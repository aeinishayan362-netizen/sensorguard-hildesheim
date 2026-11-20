import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="SensorGuard Hildesheim", page_icon="📡", layout="wide")
st.title("📡 SensorGuard Hildesheim")
st.caption("Frühwarnsystem für LoRaWAN-Sensoren · Demonstrator mit SYNTHETISCHEN Daten · keine reale Stadtanbindung")

@st.cache_data
def generate(seed=42):
    rng=np.random.default_rng(seed)
    rows=[]
    scenarios={
        'SG-001':('Innenstadt · Temperatur','gesund'),
        'SG-002':('Innerste · Wasserstand','batterie'),
        'SG-003':('Bahnhof · Luftqualität','signal'),
        'SG-004':('Stadtpark · Bodenfeuchte','luecken'),
        'SG-005':('Rathaus · Temperatur','gesund'),
        'SG-006':('Nordstadt · Luftqualität','gesund'),
        'SG-007':('Oststadt · Temperatur','batterie'),
        'SG-008':('Südstadt · Bodenfeuchte','gesund'),
        'SG-009':('Moritzberg · Wasserstand','signal'),
        'SG-010':('Itzum · Temperatur','gesund'),
        'SG-011':('Drispenstedt · Luftqualität','luecken'),
        'SG-012':('Himmelsthür · Temperatur','gesund'),
    }
    start=pd.Timestamp('2026-11-17 08:00')
    for sid,(location,scenario) in scenarios.items():
        base_battery=float(rng.uniform(65,95))
        for hour in range(72):
            t=start+pd.Timedelta(hours=hour)
            battery=base_battery-0.035*hour+rng.normal(0,0.4)
            rssi=-83+rng.normal(0,2.5)
            interval=60+rng.normal(0,2)
            if scenario=='batterie':
                battery-=0.75*hour
            if scenario=='signal':
                rssi-=0.42*hour
            if scenario=='luecken':
                interval+=max(0,hour-28)*1.25
            rows.append({'sensor_id':sid,'standort':location,'timestamp':t,'battery_pct':round(float(np.clip(battery,0,100)),2),'rssi_dbm':round(float(rssi),2),'interval_min':round(float(max(1,interval)),2),'szenario':scenario})
    return pd.DataFrame(rows)

def assess(df, threshold=35):
    result=[]
    for sid,g in df.sort_values('timestamp').groupby('sensor_id'):
        g=g.sort_values('timestamp')
        first,last=g.iloc[0],g.iloc[-1]
        days=max((last.timestamp-first.timestamp).total_seconds()/86400,0.01)
        drain=max(0,(first.battery_pct-last.battery_pct)/days)
        signal_change=float(last.rssi_dbm-first.rssi_dbm)
        interval=float(g.tail(6).interval_min.median())
        score=0; reasons=[]
        if last.battery_pct<25: score+=35;reasons.append('Batterie unter 25 %')
        if drain>10: score+=35;reasons.append(f'Batterieverlust {drain:.1f} Prozentpunkte/Tag')
        if last.rssi_dbm<-105: score+=20;reasons.append('Schwaches Empfangssignal')
        if signal_change<-15: score+=25;reasons.append('Signal verschlechtert sich deutlich')
        if interval>85: score+=35;reasons.append('Meldeintervalle werden länger')
        score=min(100,score)
        if score>=threshold: status='Kritisch'
        elif score>=30: status='Beobachten'
        else: status='Normal'
        result.append({'sensor_id':sid,'standort':last.standort,'batterie_%':round(last.battery_pct,1),'signal_dBm':round(last.rssi_dbm,1),'intervall_min':round(interval,1),'verlust_pp_tag':round(drain,1),'risiko_score':score,'status':status,'gruende':'; '.join(reasons) if reasons else 'Keine Auffälligkeit','szenario':last.szenario})
    return pd.DataFrame(result).sort_values(['risiko_score','sensor_id'],ascending=[False,True])

st.sidebar.header('Steuerung')
threshold=st.sidebar.slider('Warnschwelle (Punkte)',30,70,35,5)
st.sidebar.info('Die Risikopunkte sind erklärbare Heuristiken, keine statistischen Ausfallwahrscheinlichkeiten.')
upload=st.sidebar.file_uploader('Optional: eigene CSV importieren',type='csv')
if upload:
    try:
        df=pd.read_csv(upload)
        required={'sensor_id','standort','timestamp','battery_pct','rssi_dbm','interval_min'}
        missing=required-set(df.columns)
        if missing: raise ValueError('Fehlende Spalten: '+', '.join(sorted(missing)))
        df['timestamp']=pd.to_datetime(df['timestamp'],errors='raise')
        for c in ['battery_pct','rssi_dbm','interval_min']: df[c]=pd.to_numeric(df[c],errors='raise')
        df['szenario']='unbekannt'
        if df.empty or df.isna().any().any(): raise ValueError('Leere oder fehlende Werte in CSV')
        source='Hochgeladene CSV (Herkunft vom Nutzer zu prüfen)'
    except Exception as exc:
        st.error(f'CSV konnte nicht verarbeitet werden: {exc}')
        st.stop()
else:
    df=generate()
    source='Simulierte Demonstrationsdaten'
summary=assess(df,threshold)
critical=int((summary.status=='Kritisch').sum())
watch=int((summary.status=='Beobachten').sum())
cols=st.columns(4)
for col,label,value in zip(cols,['Sensoren','Kritisch','Beobachten','Normal'],[len(summary),critical,watch,int((summary.status=='Normal').sum())]):
    col.metric(label,value)
st.subheader('Sensorübersicht')
st.dataframe(summary[['sensor_id','standort','batterie_%','signal_dBm','intervall_min','risiko_score','status','gruende']],use_container_width=True,hide_index=True)
selected=st.selectbox('Sensor für Detailanalyse wählen',summary.sensor_id.tolist())
g=df[df.sensor_id==selected].sort_values('timestamp')
r=summary[summary.sensor_id==selected].iloc[0]
st.subheader(f'Detailanalyse · {selected}')
st.write(f"**Standort:** {r['standort']} · **Status:** {r['status']} · **Risikoscore:** {r['risiko_score']}/100")
st.write('**Erkannte Ursachen:** '+r['gruende'])
c1,c2,c3=st.columns(3)
with c1:
    st.caption('Batterie (%)')
    st.line_chart(g.set_index('timestamp')['battery_pct'])
with c2:
    st.caption('Signalstärke (dBm; niedriger = schwächer)')
    st.line_chart(g.set_index('timestamp')['rssi_dbm'])
with c3:
    st.caption('Meldeintervall (Minuten)')
    st.line_chart(g.set_index('timestamp')['interval_min'])
if r['status']=='Kritisch':
    st.error('⚠️ Wartung prüfen: '+r['gruende']+'. Zuerst Sensordaten und Empfang prüfen; anschließend bei Bedarf Vor-Ort-Einsatz planen.')
elif r['status']=='Beobachten':
    st.warning('Entwicklung beobachten und bei erneuter Auffälligkeit prüfen.')
else:
    st.success('Aktuell keine Warnung gemäß den Demo-Regeln.')
st.subheader('Validierung an simulierten Fällen')
if not upload:
    expected=summary.szenario.ne('gesund')
    predicted=summary.status.eq('Kritisch')
    tp=int((expected&predicted).sum());fp=int((~expected&predicted).sum())
    fn=int((expected&~predicted).sum());tn=int((~expected&~predicted).sum())
    st.write(f'Korrekt erkannte Fehlerszenarien: **{tp}** · Fehlalarme: **{fp}** · Übersehene Fehlerszenarien: **{fn}** · Korrekt unauffällig: **{tn}**')
    st.caption('Die Szenarien wurden gezielt erzeugt. Das ist ein Funktionstest, keine unabhängige Messung der Vorhersagegüte an echten Sensoren.')
else:
    st.info('Für importierte Daten liegen keine bestätigten Fehlerlabels vor. Daher wird keine Validierungskennzahl behauptet.')
st.download_button('Ergebnis als CSV herunterladen',summary.to_csv(index=False).encode('utf-8'),'sensorguard_ergebnisse.csv','text/csv')
st.caption('Quelle: '+source+' · Stand: Prototyp · Kein Zugriff auf städtische Sensoren · Keine automatische Benachrichtigung an die Stadt')
