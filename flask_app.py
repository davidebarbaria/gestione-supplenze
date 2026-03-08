import pandas as pd
import sqlite3
from flask import Flask, render_template_string, request, redirect

app = Flask(__name__)
DB_FILE = 'scuola.db'

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/', methods=['GET', 'POST'])
def home():
    df = pd.read_csv('EXP_COURS.csv', sep=';', dtype=str)
    giorni = sorted(df['GIORNO'].str.strip().dropna().unique().tolist())
    ore = sorted(df['O.INIZIO'].str.strip().dropna().unique().tolist())
    docenti = sorted({d.strip() for d_str in df['DOC_COGN'].dropna() for d in str(d_str).split('#') if d.strip()})
    
    r = None
    errore_copresenza = None

    if request.method == 'POST':
        g, o, a = request.form.get('giorno'), request.form.get('ora'), request.form.get('assente')
        
        # --- LOGICA COPRESENZA ---
        lezione_assente = df[(df['DOC_COGN'].str.contains(a, na=False)) & (df['GIORNO'].str.strip() == g) & (df['O.INIZIO'] == o)]
        if not lezione_assente.empty:
            classe_target = lezione_assente.iloc[0]['CLASSE']
            copresenti = df[(df['CLASSE'] == classe_target) & (df['GIORNO'].str.strip() == g) & (df['O.INIZIO'] == o) & (~df['DOC_COGN'].str.contains(a, na=False))]
            if not copresenti.empty:
                nomi_copr = ", ".join(copresenti['DOC_COGN'].unique())
                errore_copresenza = f"La classe {classe_target} è coperta da {nomi_copr} (Copresenza)."

        # --- TUA LOGICA ORIGINALE ---
        impegnati = df[(df['GIORNO'].str.strip() == g) & (df['O.INIZIO'] == o)]['DOC_COGN'].unique()
        impegnati_lista = [d.strip() for d_str in impegnati for d in str(d_str).split('#')]
        disp = df[(df['GIORNO'].str.strip() == g) & (df['O.INIZIO'] == o) & (df['MAT_NOME'] == 'DISP')]['DOC_COGN'].unique().tolist()
        liberi = [d for d in docenti if d not in impegnati_lista and d not in disp and d != a]
        r = {'giorno': g, 'ora': o, 'assente': a, 'disp': disp, 'liberi': liberi}

    # HTML RIPRISTINATO DAL TUO ORIGINALE
    html = """<!DOCTYPE html><html><head><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css"></head>
    <body class="container p-4"><div class="tabs is-toggle is-centered"><ul><li class="is-active"><a>Sostituzione</a></li><li><a href="/giornaliero">Tabellone</a></li><li><a href="/segreteria">Segreteria</a></li></ul></div>
    {% if errore %}<div class="notification is-warning is-light">{{ errore }}</div>{% endif %}
    <form method="post" class="box"><div class="field is-grouped">
    <div class="control"><div class="select"><select name="giorno">{% for val in giorni %}<option>{{ val }}</option>{% endfor %}</select></div></div>
    <div class="control"><div class="select"><select name="ora">{% for val in ore %}<option>{{ val }}</option>{% endfor %}</select></div></div>
    <div class="control"><div class="select"><select name="assente">{% for val in docenti %}<option>{{ val }}</option>{% endfor %}</select></div></div>
    <button class="button is-link">Trova Sostituto</button></div></form>
    {% if r %}<div class="box"><h2 class="subtitle">Sostituzione per {{ r.assente }} ({{ r.giorno }} ore {{ r.ora }})</h2>
    <div class="columns"><div class="column"><article class="message is-success"><div class="message-header">Disposizione</div><div class="message-body">{{ r.disp|join(', ') }}</div></article></div>
    <div class="column"><article class="message is-info"><div class="message-header">Liberi</div><div class="message-body">{{ r.liberi|join(', ') }}</div></article></div></div></div>{% endif %}</body></html>"""
    return render_template_string(html, giorni=giorni, ore=ore, docenti=docenti, r=r, errore=errore_copresenza)

@app.route('/giornaliero')
def giornaliero():
    # RIPRISTINATO IL TUO TABELLONE
    df = pd.read_csv('EXP_COURS.csv', sep=';', dtype=str)
    giorni = sorted(df['GIORNO'].str.strip().dropna().unique().tolist())
    ore = sorted(df['O.INIZIO'].str.strip().dropna().unique().tolist())
    html = """<!DOCTYPE html><html><head><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css"></head>
    <body class="container p-4"><div class="tabs is-toggle is-centered"><ul><li><a href="/">Sostituzione</a></li><li class="is-active"><a>Tabellone</a></li><li><a href="/segreteria">Segreteria</a></li></ul></div>
    <table class="table is-fullwidth is-bordered is-striped"><thead><tr><th>Ora</th>{% for g in giorni %}<th>{{ g }}</th>{% endfor %}</tr></thead>
    <tbody>{% for o in ore %}<tr><td>{{ o }}</td>{% for g in giorni %}<td>-</td>{% endfor %}</tr>{% endfor %}</tbody></table></body></html>"""
    return render_template_string(html, giorni=giorni, ore=ore)

@app.route('/segreteria', methods=['GET', 'POST'])
def segreteria():
    # RIPRISTINATA SEGRETERIA CON MENU A TENDINA
    df = pd.read_csv('EXP_COURS.csv', sep=';', dtype=str)
    docenti = sorted({d.strip() for d_str in df['DOC_COGN'].dropna() for d in str(d_str).split('#') if d.strip()})
    conn = get_db()
    if request.method == 'POST':
        conn.execute('INSERT INTO bilancio_ore (docente, ore_debito) VALUES (?, ?) ON CONFLICT(docente) DO UPDATE SET ore_debito = ore_debito + ?', 
                     (request.form.get('docente'), request.form.get('ore'), request.form.get('ore')))
        conn.commit()
    data = conn.execute('SELECT docente, ore_debito, ore_recuperate, (ore_recuperate - ore_debito) as saldo FROM bilancio_ore ORDER BY saldo DESC').fetchall()
    conn.close()
    html = """<!DOCTYPE html><html><head><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css"></head>
    <body class="container p-4"><div class="tabs is-toggle is-centered"><ul><li><a href="/">Sostituzione</a></li><li><a href="/giornaliero">Tabellone</a></li><li class="is-active"><a>Segreteria</a></li></ul></div>
    <form method="post" class="box"><div class="field has-addons">
    <div class="control is-expanded"><div class="select is-fullwidth"><select name="docente">{% for d in docenti %}<option>{{ d }}</option>{% endfor %}</select></div></div>
    <input type="number" name="ore" class="input" placeholder="Ore Debito" style="width:120px" required><button class="button is-warning">Aggiungi</button></div></form>
    <table class="table is-fullwidth is-striped"><thead><tr><th>Docente</th><th>Debito</th><th>Recuperate</th><th>Saldo</th></tr></thead>
    <tbody>{% for row in data %}<tr><td>{{ row.docente }}</td><td>{{ row.ore_debito }}</td><td>{{ row.ore_recuperate }}</td><td>{{ row.saldo }}</td></tr>{% endfor %}</tbody></table></body></html>"""
    return render_template_string(html, data=data, docenti=docenti)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
