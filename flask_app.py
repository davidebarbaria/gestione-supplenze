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
    return conn

# Manteniamo la tua logica di inizializzazione
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('CREATE TABLE IF NOT EXISTS recuperi (docente TEXT PRIMARY KEY, saldo INTEGER DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS bilancio_ore (docente TEXT PRIMARY KEY, ore_debito INTEGER DEFAULT 0)')
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def home():
    init_db()
    r = None
    errore = None
    if request.method == 'POST':
        g, o, classe = request.form.get('giorno'), request.form.get('ora'), request.form.get('classe')
        df = pd.read_csv(CSV_FILE, sep=';', dtype=str)
        
        # 1. Controllo Copresenza
        lezione = df[(df['CLASSE'] == classe) & (df['GIORNO'].str.strip() == g) & (df['O.INIZIO'] == o)]
        if len(lezione) > 1:
            docenti = [d.strip() for d_str in lezione['DOC_COGN'].dropna() for d in d_str.split('#')]
            errore = f"Attenzione: La classe {classe} è coperta da copresenza tra: {', '.join(docenti)}."
        
        # 2. Tua Logica di Ricerca (Ripristinata)
        disp = df[(df['GIORNO'].str.lower() == g.lower()) & (df['O.INIZIO'] == o) & (df['MAT_NOME'] == 'DISP')]['DOC_COGN'].unique().tolist()
        impegnati = df[(df['GIORNO'].str.lower() == g.lower()) & (df['O.INIZIO'] == o)]['DOC_COGN'].unique()
        tutti = sorted({d.strip() for d_str in df['DOC_COGN'].dropna() for d in str(d_str).split('#')})
        liberi = [d for d in tutti if d not in impegnati and d != '']
        r = {'giorno': g, 'ora': o, 'disp': disp, 'liberi': liberi}

    return render_template_string(HTML_TEMPLATE, r=r, errore=errore)

# La TUA interfaccia originale, arricchita solo con il form per segreteria
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Sostituzioni</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css">
</head>
<body class="container py-5 px-3">
    <h1 class="title has-text-centered">Gestore Sostituzioni</h1>
    
    {% if errore %}<div class="notification is-warning">{{ errore }}</div>{% endif %}

    <form method="post" class="box">
        <div class="field"><input class="input" name="giorno" placeholder="Giorno (es. lunedì)" required></div>
        <div class="field"><input class="input" name="ora" placeholder="Ora (es. 08h10)" required></div>
        <div class="field"><input class="input" name="classe" placeholder="Classe (opzionale per copresenza)"></div>
        <button class="button is-link is-fullwidth">Cerca Docenti Liberi</button>
    </form>

    {% if r %}
    <div class="box">
        <h3 class="title is-4">Risultati per {{ r.giorno }} - {{ r.ora }}</h3>
        <p><strong>In disposizione:</strong> {{ r.disp|join(', ') }}</p>
        <p><strong>Altri liberi:</strong> {{ r.liberi|join(', ') }}</p>
    </div>
    {% endif %}
</body>
</html>
"""

if __name__ == '__main__':
    app.run(debug=True)