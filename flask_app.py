import pandas as pd
import sqlite3
from flask import Flask, render_template_string, request, redirect

app = Flask(__name__)
DB_FILE = 'scuola.db'
CSV_FILE = 'EXP_COURS.csv'

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/', methods=['GET', 'POST'])
def home():
    df = pd.read_csv(CSV_FILE, sep=';', dtype=str)
    r = None
    errore = None
    
    if request.method == 'POST':
        g, o, classe = request.form.get('giorno'), request.form.get('ora'), request.form.get('classe')
        
        # 1. Controllo Copresenza
        lezione = df[(df['CLASSE'] == classe) & (df['GIORNO'].str.strip() == g) & (df['O.INIZIO'] == o)]
        if len(lezione) > 1:
            docenti = [d.strip() for d_str in lezione['DOC_COGN'].dropna() for d in d_str.split('#')]
            errore = f"La classe {classe} è coperta dai docenti: {', '.join(docenti)} (Copresenza rilevata)."
        else:
            # 2. Logica ricerca sostituti (escludendo chi è impegnato)
            impegnati = df[(df['GIORNO'].str.strip() == g) & (df['O.INIZIO'] == o)]['DOC_COGN'].unique()
            impegnati_lista = [d.strip() for d_str in impegnati for d in str(d_str).split('#')]
            tutti = sorted({d.strip() for d_str in df['DOC_COGN'].dropna() for d in str(d_str).split('#')})
            liberi = [d for d in tutti if d not in impegnati_lista]
            r = {'giorno': g, 'ora': o, 'liberi': liberi}

    return render_template_string(HTML_TEMPLATE, r=r, errore=errore)

@app.route('/segreteria', methods=['GET', 'POST'])
def segreteria():
    if request.method == 'POST':
        docente = request.form.get('docente')
        ore = int(request.form.get('ore'))
        conn = get_db()
        conn.execute('INSERT INTO bilancio_ore (docente, ore_debito) VALUES (?, ?) ON CONFLICT(docente) DO UPDATE SET ore_debito = ore_debito + ?', (docente, ore, ore))
        conn.commit()
        conn.close()
    return redirect('/segreteria')

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css"></head>
<body class="container p-4">
    <h1 class="title">Gestione Sostituzioni</h1>
    {% if errore %}<div class="notification is-warning">{{ errore }}</div>{% endif %}
    <form method="post" class="box">
        <div class="field is-grouped">
            <input class="input" name="giorno" placeholder="Giorno" required>
            <input class="input" name="ora" placeholder="Ora" required>
            <input class="input" name="classe" placeholder="Classe" required>
            <button class="button is-link">Cerca</button>
        </div>
    </form>
    {% if r %}
    <div class="box">
        <h2 class="subtitle">Docenti Liberi:</h2>
        <p>{{ r.liberi|join(', ') }}</p>
    </div>
    {% endif %}
</body>
</html>
"""

if __name__ == '__main__':
    app.run(debug=True)