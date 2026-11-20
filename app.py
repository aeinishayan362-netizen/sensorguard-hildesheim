from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title='SensorGuard | Hildesheim',page_icon='📡',layout='wide',initial_sidebar_state='expanded')
st.markdown('''<style>
.block-container{padding-top:1.4rem;max-width:1450px}h1{font-size:2.35rem!important;letter-spacing:-.035em}h2,h3{letter-spacing:-.025em}
[data-testid="stMetric"]{background:linear-gradient(135deg,#18283a,#15202d);border:1px solid #34475c;border-radius:16px;padding:18px 20px}
[data-testid="stMetricLabel"]{color:#bacbdd}[data-testid="stMetricValue"]{color:#f5f9ff}
[data-testid="stTabs"] button{font-weight:650}.hero{padding:22px 26px;border-radius:18px;background:linear-gradient(115deg,#10263b,#1a3844);border:1px solid #345567;margin-bottom:18px}
.hero small{color:#a9d8e7}.hero h2{margin:0 0 5px;color:#fff!important}.hero p{color:#c9d8e6;margin:0}
.step{border-left:3px solid #4bb5c5;padding:8px 14px;margin:10px 0;background:rgba(75,181,197,.07)}
</style>''',unsafe_allow_html=True)
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
    gap=float((now-latest['last']).total_seconds()/3600)
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

st.markdown('''<div class="hero"><small>HIZUKUNFT · DATEN-HACKATHON 2026 · CHALLENGE 03</small><h2>📡 SensorGuard Hildesheim</h2><p>Früh erkennen. Gezielt prüfen. Sensordaten sichern. — Entscheidungsunterstützung für kommunale Wartungsteams.</p></div>''',unsafe_allow_html=True)
st.caption('Analyse historischer Veranstalterdaten · keine Live-Anbindung · Warnungen sind Prüfhinweise, keine bestätigten Defekte')
d=load()
maxdate=d['last'].max();mindate=d['first'].min()
st.info(f'📅 Datenstand: {mindate:%d.%m.%Y} – {maxdate:%d.%m.%Y} (UTC) · Referenzzeitpunkt ist der letzte Datensatz, nicht die aktuelle Uhrzeit.')
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
t1,t2,t3,t4,t5=st.tabs(['🚦 Alle Sensoren & Wartung','📡 Paketverlust & Zeiträume','🔋 Batterieprognosen','📍 Gateways & Datenqualität','🎯 Jury-Demo & Validierung'])
with t1:
 st.subheader('Wartungsleitstand')
 st.write('**Was sollte das Wartungsteam zuerst tun?** Die Liste priorisiert Auffälligkeiten aus den historischen Sensordaten.')
 left,right=st.columns([1.1,1])
 with left:
  st.markdown('#### Statusverteilung')
  st.bar_chart(pd.DataFrame({'Sensoren':[(res.status==x).sum() for x in ['Rot','Gelb','Grün']]},index=['🔴 Prüfen','🟡 Beobachten','🟢 Unauffällig']))
 with right:
  st.markdown('#### Häufigste Warnhinweise')
  labels={'Meldelücke':res.grund.str.contains('Keine Meldung',regex=False).sum(),'Schwaches RSSI':res.grund.str.contains('Schwaches RSSI',regex=False).sum(),'Niedriges SNR':res.grund.str.contains('Niedriges SNR',regex=False).sum(),'Batterie niedrig':res.grund.str.contains('Niedriger gemeldeter Batteriestand',regex=False).sum(),'Messwert unverändert':res.grund.str.contains('Unveränderter Messwert',regex=False).sum()}
  st.bar_chart(pd.DataFrame({'Sensoren':list(labels.values())},index=list(labels.keys())))
 st.markdown('#### 🚦 Ampelstatus für jeden einzelnen Sensor')
 st.caption('Alle Sensoren sind mit Status und konkreter Begründung enthalten; per Statusfilter eingrenzbar.')
 st.markdown('#### 🛠️ Diese Sensoren jetzt prüfen')
 st.caption('Priorität aus transparenten Warnregeln. Ein roter Status ist ein Prüfhinweis, kein bestätigter Defekt.')
 q=st.selectbox('Status filtern',['Alle','Rot','Gelb','Grün'])
 view=res if q=='Alle' else res[res.status==q]
 st.dataframe(view[['sensor_id','typ','status','risiko_punkte','letzte_meldung','stunden_seit_meldung','rssi_dbm','snr_db','batterie_prozent','grund','empfehlung']],hide_index=True,use_container_width=True,column_config={'sensor_id':'Sensor-ID','typ':'Typ','status':'Ampel','risiko_punkte':st.column_config.ProgressColumn('Prüfscore',min_value=0,max_value=135,format='%d'),'stunden_seit_meldung':'Stunden ohne Meldung','grund':'Warum prüfen?','empfehlung':'Nächster Schritt'})
 st.caption('Mehrere Warnursachen können denselben Sensor betreffen. Die Balken sind keine voneinander unabhängigen Sensorgruppen.')
 st.download_button('📥 Wartungsliste als CSV',view.to_csv(index=False).encode('utf-8-sig'),'sensorguard_wartungsliste.csv','text/csv')
with t2:
 st.subheader('📡 Paketverlust und Übertragungslücken nach Sensor und Zeitraum')
 st.warning('Die gelieferten aggregierten Daten enthalten keine Frame Counter. Eine echte Paketverlustquote (%) ist damit **nicht berechenbar**. SensorGuard zeigt stattdessen belegte 6-Stunden-Zeitfenster und beobachtete Lücken. Das ist kein Ersatz für Paketverlust.')
 ids=(res['typ']+' | '+res['sensor_id']).tolist()
 selected=st.selectbox('Sensor auswählen',ids,key='packet_sensor')
 typ,sid=selected.split(' | ',1)
 g=filtered[(filtered.typ==typ)&(filtered.sensor_id.astype(str)==sid)].sort_values('bin')
 first=g['bin'].min().date();last=g['bin'].max().date()
 dates=st.date_input('Zeitraum auswählen',(first,last),min_value=first,max_value=last,key='packet_range')
 if isinstance(dates,(tuple,list)) and len(dates)==2:
  g=g[(g['bin'].dt.date>=dates[0])&(g['bin'].dt.date<=dates[1])]
 if g.empty:st.info('Keine Messungen im gewählten Zeitraum.')
 else:
  gaps=g['bin'].diff().dt.total_seconds().div(3600).dropna()
  c1,c2,c3=st.columns(3)
  c1.metric('Belegte 6-h-Fenster',len(g))
  c2.metric('Größte beobachtete Lücke',f'{gaps.max():.0f} h' if len(gaps) else '–')
  c3.metric('Echter Paketverlust','Nicht bestimmbar')
  st.line_chart(g.set_index('bin')[['count']].rename(columns={'count':'Empfangene Beobachtungen je 6-h-Fenster'}))
  st.caption('Die Zeitreihe enthält nur belegte Zeitfenster. Fehlende Fenster sind keine nachgewiesenen verlorenen Pakete.')
  st.dataframe(g[['bin','count','rssi','snr']].rename(columns={'bin':'Zeitfenster (UTC)','count':'Beobachtungen','rssi':'RSSI (dBm)','snr':'SNR (dB)'}),hide_index=True,use_container_width=True)
 st.info('Für echten Paketverlust pro Sensor und Zeitraum benötigen wir beispielsweise einen fortlaufenden LoRaWAN-Frame-Counter pro empfangenem Paket, inklusive Behandlung von Resets und Zählerüberläufen.')
with t3:
 st.subheader('🔋 Batterieprognose für jeden Sensor')
 st.caption('Schätzung der 20-%-Schwelle aus tatsächlich gemeldeten Prozentwerten. Kein behaupteter exakter Leerzeitpunkt.')
 battery_rows=[]
 for (typ,sid),g in filtered.groupby(['typ','sensor_id'],sort=False):
  lastpct=g.sort_values('bin')['battery_pct'].dropna()
  battery_rows.append({'Sensor-ID':sid,'Typ':typ,'Batterie aktuell (%)':round(float(lastpct.iloc[-1]),1) if len(lastpct) else np.nan,'Prognose':forecast(g)})
 bt=pd.DataFrame(battery_rows)
 st.dataframe(bt,hide_index=True,use_container_width=True)
 st.download_button('📥 Batterieprognosen als CSV',bt.to_csv(index=False).encode('utf-8-sig'),'batterieprognosen.csv','text/csv')
 st.divider()
 st.subheader('🔎 Einzelanalyse')
 options=(res['typ']+' | '+res['sensor_id']).tolist()
 selected=st.selectbox('Sensor auswählen',options,key='battery_sensor')
 typ,sid=selected.split(' | ',1)
 g=filtered[(filtered.typ==typ)&(filtered.sensor_id.astype(str)==sid)].sort_values('bin')
 r=res[(res.typ==typ)&(res.sensor_id.astype(str)==sid)].iloc[0]
 st.write(f'**Ampel:** {"🔴" if r.status=="Rot" else "🟡" if r.status=="Gelb" else "🟢"} {r.status} · **Befund:** {r.grund}')
 st.write(f'**Batterieprognose:** {forecast(g)}')
 metric=st.selectbox('Messverlauf',['battery_pct','battery_v','rssi','snr','measurement','count'])
 chart=g[['bin',metric]].dropna().set_index('bin')
 if chart.empty:st.info('Für diese Messgröße liegen keine Daten vor.')
 else:st.line_chart(chart)
 st.caption('Volt-Werte werden nicht ohne gerätespezifische Kalibrierung in Prozent umgerechnet. Eine exakte Vorhersage von 0 % ist aus diesen Daten nicht zuverlässig möglich.')
with t4:
 gateways=pd.read_csv(ROOT/'data/gateways.csv')
 st.subheader('Offizielle Gateway-Standorte')
 st.caption('Wo befinden sich Gateways? Die Karte zeigt Standorte, nicht die tatsächliche Funkabdeckung.')
 st.map(gateways,latitude='lat',longitude='long',zoom=11)
 st.dataframe(gateways,hide_index=True,use_container_width=True)
 st.caption('Die Daten enthalten Gateway-Koordinaten, aber keine belastbare Zuordnung jedes Sensors zu einem Gateway. Keine Funkabdeckung wird behauptet.')
 st.image(str(ROOT/'data/Gateway_Karte.png'),caption='Von den Veranstaltern bereitgestellte Gateway-Karte')
with t4:
 st.subheader('Datenprofil')
 st.dataframe(pd.read_csv(ROOT/'data/datenprofil.csv'),hide_index=True,use_container_width=True)
 st.markdown('''**Methodik:** Originale Rohdatensätze wurden ohne erfundene Messwerte in 6-Stunden-Zeitfenster zusammengefasst. Die Zahl der Beobachtungen und Mediane sind aus den bereitgestellten CSV-Dateien berechnet. Die Zeitfensteraggregation kann kurze Ausfälle verbergen. Warnregeln für RSSI, SNR, Meldelücken und gemeldeten Batteriestand sind demonstrative Heuristiken, keine amtlichen Grenzwerte.\n\n**Grenzen:** Kein Frame Counter, keine validierte Paketverlustrate, keine sichere Geräte-Gateway-Zuordnung, keine echte automatische Alarmzustellung, keine unabhängig validierte Vorhersagegenauigkeit. Batterieprognosen nur bei ausreichend langen, plausiblen Prozent-Zeitreihen. ''')
 st.download_button('📥 Aggregierte Messdaten herunterladen',(ROOT/'data/sensor_6h.csv.gz').read_bytes(),'sensor_6h.csv.gz','application/gzip')

with t5:
 st.subheader('Jury-Demo: Vom Messsignal zur Wartungsentscheidung')
 st.markdown('**Szenario:** Ein Sensor meldet sich ungewöhnlich lange nicht und zeigt gleichzeitig schwache Funkwerte. SensorGuard ordnet den Fall in die Wartungsliste ein. Die Jury kann die zugrunde liegende Messreihe im Tab „Sensor-Check“ prüfen.')
 top=res.iloc[0]
 st.markdown(f'<div class="step"><b>1 · Erkennen</b><p>Sensor {top.sensor_id} · Typ: {top.typ} · {top.stunden_seit_meldung:.0f} Stunden seit letzter Meldung</p></div>',unsafe_allow_html=True)
 st.markdown(f'<div class="step"><b>2 · Begründen</b><p>{top.grund}</p></div>',unsafe_allow_html=True)
 st.markdown(f'<div class="step"><b>3 · Handeln</b><p>{top.empfehlung}. Wartungsliste als CSV exportieren und an das zuständige Team übergeben.</p></div>',unsafe_allow_html=True)
 st.divider()
 st.subheader('Technische Plausibilitätsprüfung')
 st.write('Die folgenden Prüfungen zeigen, ob die Auswertung intern konsistent ist. **Sie beweisen keine rechtzeitige Vorhersage realer Ausfälle.**')
 tests={
  'Jeder Sensor hat genau eine Ampelfarbe':len(res)==len(res[['typ','sensor_id']].drop_duplicates()),
  'Statussummen entsprechen der Sensorzahl':sum((res.status==x).sum() for x in ['Rot','Gelb','Grün'])==len(res),
  'Warnscores sind nicht negativ':bool((res.risiko_punkte>=0).all()),
  'Letzte Meldungen liegen nicht nach dem Datenstand':bool((res.letzte_meldung<=maxdate).all()),
  'Wartungsliste ist nach Priorität sortiert':bool(res.risiko_punkte.is_monotonic_decreasing)
 }
 for name,passed in tests.items():st.write(('✅' if passed else '❌')+' '+name)
 st.divider()
 st.subheader('Validierung gegen Wartungsprotokoll')
 st.warning('Noch nicht nachgewiesen: Ob SensorGuard bekannte Ausfälle **vor** dem dokumentierten Ausfallzeitpunkt erkannt hätte. Dafür werden Ereigniszeitpunkte und betroffene Sensor-IDs aus dem Wartungsprotokoll benötigt.')
 st.markdown('**So wird korrekt validiert:** Protokoll mit Sensor-ID und Ereigniszeit einlesen → Warnregeln ausschließlich auf Daten **vor** dem Ereignis anwenden → Vorwarnzeit, erkannte Ausfälle, übersehene Ausfälle und Fehlalarme berechnen → Ergebnisse offen präsentieren. Ohne diese Daten werden keine Erfolgsquoten erfunden.')
 st.markdown('#### Integration in den städtischen Betrieb')
 st.markdown('**Datenexport → automatisierte Auswertung → priorisierte Wartungsliste → manuelle technische Prüfung → dokumentierte Rückmeldung.** Die aktuelle Version demonstriert den Analyse- und Exportteil; eine echte Schnittstelle zur Stadt ist noch nicht vorhanden.')
 st.caption('Optionaler Ausbau: automatische Benachrichtigung, tägliche Ausführung und Anomalieerkennung nach unabhängiger Validierung.')
