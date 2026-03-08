import pandas as pd
import sqlite3
import os
from flask import Flask, render_template_string, request, redirect

app = Flask(__name__)
CSV_FILE = 'EXP_COURS.csv'
DB_FILE = 'scuola.db'

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    # Assicuriamoci che le tabelle esistano
    conn.execute('CREATE TABLE IF NOT EXISTS bilancio_ore (docente TEXT PRIMARY KEY, ore_debito INTEGER DEFAULT 0, ore_recuperate INTEGER DEFAULT 0)')
    return conn

# Funzione per estrarre i docenti dal CSV (usata in tutte le pagine)
def get_lista_docenti():
    if not os.path.exists(CSV_FILE):
        return []
    df = pd.read_csv(CSV_FILE, sep=';', dtype=str)
    # Estraiamo i nomi gestendo anche i separatori '#'
    docenti = sorted({d.strip() for d_str in df['DOC_COGN'].dropna() for d in str(d_str).split('#') if d.strip()})
    return docenti

@app.route('/', methods=['GET', 'POST'])
def home():
    df = pd.read_csv(CSV_FILE, sep=';', dtype=str)
    giorni = sorted(df['GIORNO'].str.strip().dropna().unique().tolist())
    ore = sorted(df['O.INIZIO'].str.strip().dropna().unique().tolist())
    docenti = get_lista_docenti()
    
    r = None
    errore_copresenza = None

    if request.method == 'POST':
        g, o, a = request.form.get('giorno'), request.form.get('ora'), request.form.get('assente')
        
        # LOGICA COPRESENZA
        lezione_assente = df[(df['DOC_COGN'].str.contains(a, na=False)) & (df['GIORNO'].str.strip() == g) & (df['O.INIZIO'] == o)]
        if not lezione_assente.empty:
            classe_target = lezione_assente.iloc[0]['CLASSE']
            copresenti = df[(df['CLASSE'] == classe_target) & (df['GIORNO'].str.strip() == g) & (df['O.INIZIO'] == o) & (~df['DOC_COGN'].str.contains(a, na=False))]
            if not copresenti.empty:
                nomi_copr = ", ".join(copresenti['DOC_COGN'].unique())
                errore_copresenza = f"La classe {classe_target} è coperta da {nomi_copr} (Copresenza)."

        # LOGICA RICERCA
        impegnati = df[(df['GIORNO'].str.strip() == g) & (df['O.INIZIO'] == o)]['DOC_COGN'].unique()
        impegnati_lista = [d.strip() for d_str in impegnati for d in str(d_str).split('#')]
        disp = df[(df['GIORNO'].str.strip() == g) & (df['O.INIZIO'] == o) & (df['MAT_NOME'] == 'DISP')]['DOC_COGN'].unique().tolist()
        liberi = [d for d in docenti if d not in impegnati_lista and d not in disp and d != a]
        r = {'giorno': g, 'ora': o, 'assente': a, 'disp': disp, 'liberi': liberi}

    return render_template_string(HTML_MAIN, giorni=giorni, ore=ore, docenti=docenti, r=r, errore=errore_copresenza)

@app.route('/segreteria', methods=['GET', 'POST'])
def segreteria():
    docenti = get_lista_docenti()
    conn = get_db()
    
    if request.method == 'POST':
        docente = request.form.get('docente')
        ore = request.form.get('ore')
        if docente and ore:
            conn.execute('''INSERT INTO bilancio_ore (docente, ore_debito) VALUES (?, ?) 
                            ON CONFLICT(docente) DO UPDATE SET ore_debito = ore_debito + ?''', 
                         (docente, ore, ore))
            conn.commit()
    
    data = conn.execute('SELECT docente, ore_debito, ore_recuperate, (ore_recuperate - ore_debito) as saldo FROM bilancio_ore ORDER BY docente ASC').fetchall()
    conn.close()
    return render_template_string(HTML_SEGRETERIA, docenti=docenti, data=data)

# --- TEMPLATE ---

HTML_MAIN = """
<!DOCTYPE html><html lang="it"><head><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css"></head>
<body class="container p-4">
    <div class="tabs is-toggle is-centered"><ul><li class="is-active"><a href="/">Sostituzione</a></li><li><a href="/segreteria">Segreteria</a></li></ul></div>
    {% if errore %}<div class="notification is-warning">{{ errore }}</div>{% endif %}
    <form method="post" class="box">
        <div class="field is-grouped is-grouped-multiline">
            <div class="control"><div class="select"><select name="giorno">{% for g in giorni %}<option>{{ g }}</option>{% endfor %}</select></div></div>
            <div class="control"><div class="select"><select name="ora">{% for o in ore %}<option>{{ o }}</option>{% endfor %}</select></div></div>
            <div class="control"><div class="select"><select name="assente">{% for d in docenti %}<option>{{ d }}</option>{% endfor %}</select></div></div>
            <div class="control"><button class="button is-link">Trova Sostituto</button></div>
        </div>
    </form>
    {% if r %}
    <div class="box">
        <h2 class="subtitle">Sostituzione per {{ r.assente }} ({{ r.giorno }} ore {{ r.ora }})</h2>
        <div class="columns">
            <div class="column"><article class="message is-success"><div class="message-header">Disposizione</div><div class="message-body">{{ r.disp|join(', ') }}</div></article></div>
            <div class="column"><article class="message is-info"><div class="message-header">Liberi</div><div class="message-body">{{ r.liberi|join(', ') }}</div></article></div>
        </div>
    </div>
    {% endif %}
</body></html>
"""

HTML_SEGRETERIA = """
<!DOCTYPE html><html lang="it"><head><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css"></head>
<body class="container p-4">
    <div class="tabs is-toggle is-centered"><ul><li><a href="/">Sostituzione</a></li><li class="is-active"><a href="/segreteria">Segreteria</a></li></ul></div>
    <form method="post" class="box">
        <h3 class="subtitle">Registra Assenza (Debito Ore)</h3>
        <div class="field has-addons">
            <div class="control is-expanded"><div class="select is-fullwidth"><select name="docente" required>
                <option value="">Seleziona Docente...</option>
                {% for d in docenti %}<option value="{{ d }}">{{ d }}</option>{% endfor %}
            </select></div></div>
            <div class="control"><input type="number" name="ore" class="input" placeholder="Ore" required></div>
            <div class="control"><button class="button is-danger">Aggiungi Debito</button></div>
        </div>
    </form>
    <table class="table is-fullwidth is-striped is-hoverable">
        <thead><tr><th>Docente</th><th>Ore Debito</th><th>Ore Recuperate</th><th>Saldo</th></tr></thead>
        <tbody>
            {% for row in data %}
            <tr><td>{{ row.docente }}</td><td>{{ row.ore_debito }}</td><td>{{ row.ore_recuperate }}</td><td>{{ row.saldo }}</td></tr>
            {% endfor %}
        </tbody>
    </table>
</body></html>
"""

if __name__ == '__main__':
    # Ricorda: se lo usi in locale, metti app.run(host='0.0.0.0', port=5000)
    app.run(debug=True)
