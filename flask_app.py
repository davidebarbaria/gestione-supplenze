import pandas as pd
import sqlite3
from flask import Flask, render_template_string, request, redirect

app = Flask(__name__)
DB_FILE = 'scuola.db'

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('CREATE TABLE IF NOT EXISTS recuperi (docente TEXT PRIMARY KEY, saldo INTEGER DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS registro (id INTEGER PRIMARY KEY AUTOINCREMENT, giorno_lezione TEXT, ora_lezione TEXT, classe TEXT, assente TEXT, sostituto TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS bilancio_ore (docente TEXT PRIMARY KEY, ore_debito INTEGER DEFAULT 0, ore_recuperate INTEGER DEFAULT 0)')
    return conn

@app.route('/', methods=['GET', 'POST'])
def home():
    df = pd.read_csv('EXP_COURS.csv', sep=';', dtype=str)
    giorni = sorted(df['GIORNO'].str.strip().dropna().unique().tolist())
    ore = sorted(df['O.INIZIO'].str.strip().dropna().unique().tolist())
    docenti = sorted({d.strip() for d_str in df['DOC_COGN'].dropna() for d in str(d_str).split('#') if d.strip()})
    
    r = None
    if request.method == 'POST':
        g, o, a = request.form.get('giorno'), request.form.get('ora'), request.form.get('docente_assente')
        riga = df[(df['GIORNO'].str.strip() == g) & (df['O.INIZIO'].str.strip() == o) & (df['DOC_COGN'].str.contains(a, na=False))]
        if not riga.empty:
            r = {'g': g, 'o': o, 'a': a, 'classe': str(riga.iloc[0].get('CLASSE', 'N/D'))}
            
    html = """<!DOCTYPE html><html><head><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css"></head>
    <body class="container p-4"><div class="tabs is-toggle is-centered"><ul><li class="is-active"><a>Sostituzione</a></li><li><a href="/giornaliero">Tabellone</a></li><li><a href="/segreteria">Segreteria</a></li></ul></div>
    <form method="post" class="box"><label class="label">Docente Assente</label><div class="select is-fullwidth mb-3"><select name="docente_assente" required>{% for x in docenti %}<option value="{{ x }}">{{ x }}</option>{% endfor %}</select></div>
    <div class="columns"><div class="column"><label class="label">Giorno</label><div class="select is-fullwidth"><select name="giorno">{% for x in giorni %}<option value="{{ x }}">{{ x }}</option>{% endfor %}</select></div></div>
    <div class="column"><label class="label">Ora</label><div class="select is-fullwidth"><select name="ora">{% for x in ore %}<option value="{{ x }}">{{ x }}</option>{% endfor %}</select></div></div></div>
    <button class="button is-primary is-fullwidth">Cerca Classe</button></form>
    {% if r %}<form action="/assegna" method="post" class="box has-background-light"><p>Classe trovata: <b>{{ r.classe }}</b></p>
    <input type="hidden" name="giorno" value="{{r.g}}"><input type="hidden" name="ora" value="{{r.o}}"><input type="hidden" name="classe" value="{{r.classe}}"><input type="hidden" name="assente" value="{{r.a}}">
    <div class="select is-fullwidth mb-3"><select name="sostituto" required><option value="" disabled selected>Sostituto</option>{% for x in docenti %}<option value="{{ x }}">{{ x }}</option>{% endfor %}</select></div>
    <button class="button is-success is-fullwidth">Registra</button></form>{% endif %}</body></html>"""
    return render_template_string(html, giorni=giorni, ore=ore, docenti=docenti, r=r)

@app.route('/assegna', methods=['POST'])
def assegna():
    s, g, o, c, a = request.form.get('sostituto'), request.form.get('giorno'), request.form.get('ora'), request.form.get('classe'), request.form.get('assente')
    conn = get_db()
    conn.execute('INSERT INTO registro (giorno_lezione, ora_lezione, classe, assente, sostituto) VALUES (?, ?, ?, ?, ?)', (g, o, c, a, s))
    conn.execute('INSERT INTO bilancio_ore (docente, ore_recuperate) VALUES (?, 1) ON CONFLICT(docente) DO UPDATE SET ore_recuperate = ore_recuperate + 1', (s,))
    conn.commit(); conn.close()
    return redirect('/giornaliero')

@app.route('/giornaliero')
def giornaliero():
    conn = get_db()
    data = conn.execute('SELECT giorno_lezione, ora_lezione, classe, assente, sostituto FROM registro ORDER BY id DESC').fetchall()
    conn.close()
    html = """<!DOCTYPE html><html><head><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css"></head>
    <body class="container p-4"><div class="tabs is-toggle is-centered"><ul><li><a href="/">Sostituzione</a></li><li class="is-active"><a>Tabellone</a></li><li><a href="/segreteria">Segreteria</a></li></ul></div>
    <table class="table is-fullwidth is-striped"><thead><tr><th>Giorno</th><th>Ora</th><th>Classe</th><th>Assente</th><th>Sostituto</th></tr></thead>
    <tbody>{% for x in data %}<tr><td>{{x[0]}}</td><td>{{x[1]}}</td><td>{{x[2]}}</td><td>{{x[3]}}</td><td><b>{{x[4]}}</b></td></tr>{% endfor %}</tbody></table></body></html>"""
    return render_template_string(html, data=data)

@app.route('/segreteria', methods=['GET', 'POST'])
def segreteria():
    conn = get_db()
    if request.method == 'POST':
        conn.execute('INSERT INTO bilancio_ore (docente, ore_debito) VALUES (?, ?) ON CONFLICT(docente) DO UPDATE SET ore_debito = ore_debito + ?', 
                     (request.form.get('docente'), request.form.get('ore'), request.form.get('ore')))
        conn.commit()
    data = conn.execute('SELECT docente, ore_debito, ore_recuperate, (ore_recuperate - ore_debito) as saldo FROM bilancio_ore ORDER BY saldo DESC').fetchall()
    conn.close()
    html = """<!DOCTYPE html><html><head><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css"></head>
    <body class="container p-4"><div class="tabs is-toggle is-centered"><ul><li><a href="/">Sostituzione</a></li><li><a href="/giornaliero">Tabellone</a></li><li class="is-active"><a>Segreteria</a></li></ul></div>
    <form method="post" class="box"><div class="field has-addons"><input type="text" name="docente" class="input" placeholder="Nome Docente" required>
    <input type="number" name="ore" class="input" placeholder="Ore Permesso" required><button class="button is-warning">Aggiungi Debito</button></div></form>
    <table class="table is-fullwidth is-striped"><thead><tr><th>Docente</th><th>Debito</th><th>Recuperate</th><th>Saldo (Netto)</th></tr></thead>
    <tbody>{% for x in data %}<tr><td>{{x[0]}}</td><td>{{x[1]}}</td><td>{{x[2]}}</td><td><b>{{x[3]}}</b></td></tr>{% endfor %}</tbody></table></body></html>"""
    return render_template_string(html, data=data)

if __name__ == '__main__': app.run()