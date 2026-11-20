from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title='SensorGuard | Hildesheim',page_icon='📡',layout='wide')
ROOT=Path(__file__).resolve().parent
@st.cache_data(show_spinner='Lade echte Messdaten …')
def load():
    d=pd.read_csv(ROOT/'data/sensor_6h.csv.gz',parse_dates=['bin','first','last'])
    for c in ['rssi','snr','battery_pct','battery_v','measurement']:
        d[c]=pd.to_numeric(d[c],errors='coerce')
    return d

def assess(g,now,gap_factor,signal_limit):
    g=g.sort_values('bin'); latest=g.iloc[-1]; sid=str(latest.sensor_id)
    intervals=g['bin'].diff().dt.total_seconds().div(3600).dropna()
    typical=float(intervals[intervals>0].median()) if len(intervals[intervals>0]) else np.nan
    gap = float((pd.to_datetime(now, utc=True) - pd.to_datetime(last['last'], utc=True)).total_seconds() / 3600)
    reasons=[];score=0
    if np.isfinite(typical) and gap>max(24,typical*gap_factor):reasons.append(f'Keine Meldung seit {gap:.0f} h (üblicher Abstand der belegten Zeitfenster: {typical:.0f} h)');score+=45
    if pd.notna(latest.rssi) and latest.rssi<signal_limit:reasons.append(f'Schwaches RSSI: {latest.rssi:.1f} dBm');score+=25
    if pd.notna(latest.snr) and latest.snr < -12:reasons.append(f'Niedriges SNR: {latest.snr:.1f} dB');score+=20
    if pd.notna(latest.battery_pct) and 0<=latest.battery_pct<=20:reasons.append(f'Niedriger gemeldeter Batteriestand: {latest.battery_pct:.1f} %');score+=30
    # heuristic for frozen values: only when multiple populated consecutive bins, not a diagnosis
    recent=g.tail(8).measurement.dropna()
    if len(recent)>=6 and recent.nunique()==1:reasons.append('Unveränderter Messwert in mindestens sechs 6-Stunden-Fenstern (prüfen)');score+=15
    status='Rot' if score>=40 else 'Gelb' if score>=20 else 'Grün'
    return {'sensor_id':sid,'typ':latest.typ,'status':status,'risiko_punkte':score,'letzte_meldung':latest['last'],'stunden_seit_meldung':round(gap,1),'rssi_dbm':latest.rssi,'snr_db':latest.snr,'batterie_prozent':latest.battery_pct,'batterie_volt':latest.battery_v,'beobachtungen':int(g['count'].sum()),'grund':'; '.join(reasons) if reasons else 'Keine Auffälligkeit nach den gewählten Regeln','empfehlung':'Datenverbindung und Gerät prüfen' if score>=40 else 'Messverlauf beobachten' if score>=20 else 'Keine unmittelbare Maßnahme'}

def forecast(g):
    # battery % forecast only; voltage is NOT a percent, no fabricated conversion
    p=g[['bin','battery_pct']].dropna().sort_values('bin').tail(35)
    if len(p)<8:return 'Nicht möglich: zu wenige Prozentwerte'
    if p.bin.max()-p.bin.min()<pd.Timedelta(days=7):return 'Nicht möglich: Zeitraum unter 7 Tagen'
    x=(p.bin-p.bin.min()).dt.total_seconds().to_numpy()/86400
    y=p.battery_pct.to_numpy(dtype=float)
    if np.nanmin(y)<0 or np.nanmax(y)>100:return 'Nicht möglich: ungültige Prozentwerte'
    slope=float(np.polyfit(x,y,1)[0]);pred=np.polyval(np.polyfit(x,y,1),x)
    if slope>=-0.02:return 'Keine belastbare Abnahme erkennbar'
    if np.std(y-pred)>max(5,np.ptp(y)*0.4):return 'Zu stark schwankender Batterieverlauf'
    days=(float(y[-1])-20)/(-slope)
    if days<0:return '20-%-Grenze bereits unterschritten'
    if days>365:return 'Prognose über 365 Tage: zu unsicher'
    return f'20-%-Schwelle in ungefähr {days:.0f} Tagen (lineare Extrapolation, keine Garantie)'

st.title('📡 SensorGuard Hildesheim')
st.caption('Challenge 3 · Frühwarnsystem auf Basis der bereitgestellten Hackathon-Messdaten · historische Daten, keine Live-Stadtanbindung')
d=load()
maxdate=d['last'].max();mindate=d['first'].min()
st.info(f"Historische Messdaten: {mindate} bis {maxdate} (UTC). Die Bewertung erfolgt relativ zum letzten vorhandenen Datensatz, nicht zur aktuellen Uhrzeit.")
with st.sidebar:
 st.header('⚙️ Prüfregeln')
 signal_limit=st.slider('RSSI-Warnschwelle (dBm)',-130,-70,-110)
 gap_factor=st.slider('Lückenfaktor gegenüber typischem Abstand',2.0,8.0,3.0,0.5)
 types=st.multiselect('Sensortypen',sorted(d.typ.unique()),default=sorted(d.typ.unique()))
 st.caption('Regeln sind konfigurierbare Heuristiken, keine kalibrierten Ausfallwahrscheinlichkeiten.')
 st.warning('Kein Frame Counter in den gelieferten Tabellen: tatsächliche Paketverlustrate kann nicht seriös berechnet werden.')
filtered=d[d.typ.isin(types)]
if filtered.empty:st.warning('Bitte mindestens einen Typ wählen.');st.stop()
# Grouped 6-hour windows are a compressed representation of actual measurements
rows=[assess(g,maxdate,gap_factor,signal_limit) for _,g in filtered.groupby(['typ','sensor_id'],sort=False)]
res=pd.DataFrame(rows).sort_values(['risiko_punkte','stunden_seit_meldung'],ascending=[False,False])
a,b,c,e=st.columns(4)
a.metric('Sensoren',len(res));b.metric('🔴 Prüfen',int((res.status=='Rot').sum()));c.metric('🟡 Beobachten',int((res.status=='Gelb').sum()));e.metric('🟢 Unauffällig',int((res.status=='Grün').sum()))
t1,t2,t3,t4=st.tabs(['🚦 Sensorübersicht','🔎 Einzelanalyse','📍 Gateways','🧪 Datenqualität & Methodik'])
with t1:
 st.subheader('Priorisierte Wartungsliste')
 st.caption('Priorität aus transparenten Warnregeln. Ein roter Status ist ein Prüfhinweis, kein bestätigter Defekt.')
 q=st.selectbox('Status filtern',['Alle','Rot','Gelb','Grün'])
 view=res if q=='Alle' else res[res.status==q]
 st.dataframe(view[['sensor_id','typ','status','risiko_punkte','letzte_meldung','stunden_seit_meldung','rssi_dbm','snr_db','batterie_prozent','grund','empfehlung']],hide_index=True,use_container_width=True)
 st.download_button('📥 Wartungsliste als CSV',view.to_csv(index=False).encode('utf-8-sig'),'sensorguard_wartungsliste.csv','text/csv')
with t2:
 options=(res['typ']+' | '+res['sensor_id']).tolist()
 selected=st.selectbox('Sensor auswählen',options)
 typ,sid=selected.split(' | ',1)
 g=filtered[(filtered.typ==typ)&(filtered.sensor_id.astype(str)==sid)].sort_values('bin')
 r=res[(res.typ==typ)&(res.sensor_id.astype(str)==sid)].iloc[0]
 st.write(f"**Status: {r.status}** · {r.grund}")
 st.write(f"**Batterieprognose:** {forecast(g)}")
 st.caption('Nur aus tatsächlich gemeldeten Batterie-Prozentwerten. Spannung in Volt wird nicht willkürlich in Prozent umgerechnet.')
 metric=st.selectbox('Messverlauf',['rssi','snr','battery_pct','battery_v','measurement','count'])
 chart=g[['bin',metric]].dropna().set_index('bin')
 if chart.empty:st.warning('Für diesen Sensor liegen keine Werte für diese Messgröße vor.')
 else:st.line_chart(chart)
 st.caption('Die Kurven zeigen Medianwerte je 6-Stunden-Fenster (count = Anzahl Beobachtungen), keine interpolierten Rohdaten.')
 st.subheader('Beobachtete Übertragungslücken')
 gaps=g['bin'].diff().dt.total_seconds().div(3600).dropna()
 st.write(f'Größter Abstand zwischen belegten 6-Stunden-Fenstern: **{gaps.max():.0f} Stunden**' if len(gaps) else 'Nicht genug Daten für eine Lückenanalyse.')
 st.warning('Eine Messlücke ist kein beweisbarer Paketverlust. Ohne Frame Counter oder bekannte Sendeintervalle ist keine echte Paketverlustquote berechenbar.')
with t3:
 gateways=pd.read_csv(ROOT/'data/gateways.csv')
 st.subheader('Offizielle Gateway-Standorte')
 st.map(gateways,latitude='lat',longitude='long',zoom=11)
 st.dataframe(gateways,hide_index=True,use_container_width=True)
 st.caption('Die Daten enthalten Gateway-Koordinaten, aber keine belastbare Zuordnung jedes Sensors zu einem Gateway. Keine Funkabdeckung wird behauptet.')
 st.image(str(ROOT/'data/Gateway_Karte.png'),caption='Von den Veranstaltern bereitgestellte Gateway-Karte')
with t4:
 st.subheader('Datenprofil')
 st.dataframe(pd.read_csv(ROOT/'data/datenprofil.csv'),hide_index=True,use_container_width=True)
 st.markdown('''**Methodik:** Originale Rohdatensätze wurden ohne erfundene Messwerte in 6-Stunden-Zeitfenster zusammengefasst. Die Zahl der Beobachtungen und Mediane sind aus den bereitgestellten CSV-Dateien berechnet. Die Zeitfensteraggregation kann kurze Ausfälle verbergen. Warnregeln für RSSI, SNR, Meldelücken und gemeldeten Batteriestand sind demonstrative Heuristiken, keine amtlichen Grenzwerte.\n\n**Grenzen:** Kein Frame Counter, keine validierte Paketverlustrate, keine sichere Geräte-Gateway-Zuordnung, keine echte automatische Alarmzustellung, keine unabhängig validierte Vorhersagegenauigkeit. Batterieprognosen nur bei ausreichend langen, plausiblen Prozent-Zeitreihen. ''')
 st.download_button('📥 Aggregierte Messdaten herunterladen',(ROOT/'data/sensor_6h.csv.gz').read_bytes(),'sensor_6h.csv.gz','application/gzip')
