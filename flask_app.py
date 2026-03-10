import pandas as pd
import sqlite3
import os
from flask import Flask, render_template_string, request, redirect

app = Flask(__name__)
DB_FILE = 'scuola.db'

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('CREATE TABLE IF NOT EXISTS registro (id INTEGER PRIMARY KEY AUTOINCREMENT, giorno_lezione TEXT, ora_lezione TEXT, classe TEXT, assente TEXT, sostituto TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS bilancio_ore (docente TEXT PRIMARY KEY, ore_debito INTEGER DEFAULT 0, ore_recuperate INTEGER DEFAULT 0)')
    return conn

@app.route('/', methods=['GET', 'POST'])
def home():
    df = pd.read_csv('EXP_COURS.csv', sep=';', dtype=str)
    giorni = sorted(df['GIORNO'].str.strip().dropna().unique().tolist())
    ore = sorted(df['O.INIZIO'].str.strip().dropna().unique().tolist())
    
    risultato = None
    avviso_copresenza = None

    if request.method == 'POST':
        g = request.form.get('giorno')
        o = request.form.get('ora')
        a = request.form.get('docente_assente')

        lezione = df[(df['GIORNO'] == g) & (df['O.INIZIO'] == o) & (df['DOC_COGN'].str.contains(a, na=False, case=False))]
        
        if not lezione.empty:
            classe_target = lezione.iloc[0]['CLASSE']
            docenti_ora = lezione.iloc[0]['DOC_COGN']
            lista_docenti = [d.strip() for d in docenti_ora.split('#')]
            if len(lista_docenti) > 1:
                altri = [d for d in lista_docenti if d.lower() != a.lower()]
                avviso_copresenza = f"ATTENZIONE: In classe {classe_target} è presente il co-docente: {', '.join(altri)}."

            sostituti = df[(df['GIORNO'] == g) & (df['O.INIZIO'] == o) & (df['MAT_NOME'].str.contains('DISP|Z_', na=False, case=False))]
            lista_sostituti = sostituti['DOC_COGN'].unique().tolist()
            
            risultato = {'classe': classe_target, 'sostituti': lista_sostituti, 'assente': a}

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css"><title>Gestione Supplenze</title></head>
    <body class="container p-4">
        <div class="tabs is-toggle is-centered"><ul><li class="is-active"><a href="/">Sostituzione</a></li><li><a href="/segreteria">Segreteria</a></li></ul></div>
        <form method="post" class="box">
            <div class="columns">
                <div class="column"><label>Giorno</label><div class="select is-fullwidth"><select name="giorno">{% for g in giorni %}<option>{{ g }}</option>{% endfor %}</select></div></div>
                <div class="column"><label>Ora</label><div class="select is-fullwidth"><select name="ora">{% for o in ore %}<option>{{ o }}</option>{% endfor %}</select></div></div>
                <div class="column"><label>Docente Assente</label><input type="text" name="docente_assente" class="input" required></div>
            </div>
            <button class="button is-link is-fullwidth">Cerca Sostituto</button>
        </form>
        {% if avviso_copresenza %}<div class="notification is-warning">{{ avviso_copresenza }}</div>{% endif %}
        {% if risultato %}
            <div class="box"><h3 class="title is-4">Classe {{ risultato.classe }}</h3><ul>
                {% for s in risultato.sostituti %}<li>{{ s }}</li>{% endfor %}
            </ul></div>
        {% endif %}
    </body>
    </html>
    """, giorni=giorni, ore=ore, risultato=risultato, avviso_copresenza=avviso_copresenza)

@app.route('/segreteria', methods=['GET', 'POST'])
def segreteria():
    df = pd.read_csv('EXP_COURS.csv', sep=';', dtype=str)
    lista_completa_docenti = sorted({d.strip() for d_str in df['DOC_COGN'].dropna() for d in str(d_str).split('#') if d.strip()})
    conn = get_db()
    if request.method == 'POST':
        docente = request.form.get('docente')
        ore_v = int(request.form.get('ore'))
        conn.execute('INSERT INTO bilancio_ore (docente, ore_debito) VALUES (?, ?) ON CONFLICT(docente) DO UPDATE SET ore_debito = ore_debito + ?', (docente, ore_v, ore_v))
        conn.commit()
    dati = conn.execute('SELECT docente, ore_debito, ore_recuperate, (ore_recuperate - ore_debito) as saldo FROM bilancio_ore ORDER BY saldo ASC').fetchall()
    conn.close()

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css"></head>
    <body class="container p-4">
        <div class="tabs is-toggle is-centered"><ul><li><a href="/">Sostituzione</a></li><li class="is-active"><a href="/segreteria">Segreteria</a></li></ul></div>
        <form method="post" class="box">
            <h3 class="subtitle">Aggiungi Debito Orario</h3>
            <div class="field has-addons">
                <div class="control is-expanded"><div class="select is-fullwidth"><select name="docente" required><option value="">Seleziona...</option>{% for d in docenti %}<option value="{{ d }}">{{ d }}</option>{% endfor %}</select></div></div>
                <div class="control"><input type="number" name="ore" class="input" placeholder="Ore" required></div>
                <div class="control"><button class="button is-danger">Aggiungi</button></div>
            </div>
        </form>
        <table class="table is-fullwidth is-striped">
            <thead><tr><th>Docente</th><th>Debito</th><th>Recuperate</th><th>Saldo</th></tr></thead>
            <tbody>{% for d in dati %}<tr><td>{{ d[0] }}</td><td>{{ d[1] }}</td><td>{{ d[2] }}</td><td class="{% if d[3] < 0 %}has-text-danger{% else %}has-text-success{% endif %}"><b>{{ d[3] }}</b></td></tr>{% endfor %}</tbody>
        </table>
    </body>
    </html>
    """, docenti=lista_completa_docenti, dati=dati)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
