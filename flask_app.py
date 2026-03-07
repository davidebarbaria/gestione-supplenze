import pandas as pd
import sqlite3
import os
from flask import Flask, render_template_string, request

app = Flask(__name__)
CSV_FILE = 'EXP_COURS.csv'
DB_FILE = 'scuola.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''CREATE TABLE IF NOT EXISTS recuperi 
                    (docente TEXT PRIMARY KEY, saldo INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def trova_sostituti(giorno, ora):
    if not os.path.exists(CSV_FILE):
        return [], [], "Errore: File CSV non trovato!"
    
    df = pd.read_csv(CSV_FILE, sep=';')
    df['DOC_COGN'] = df['DOC_COGN'].fillna('').str.strip()
    
    disp = df[(df['GIORNO'].str.lower() == giorno.lower()) & 
              (df['O.INIZIO'] == ora) & 
              (df['MAT_NOME'] == 'DISP')]['DOC_COGN'].unique().tolist()
    
    impegnati = df[(df['GIORNO'].str.lower() == giorno.lower()) & 
                   (df['O.INIZIO'] == ora)]['DOC_COGN'].unique()
    tutti = df['DOC_COGN'].unique()
    liberi = [d for d in tutti if d not in impegnati and d != '']
    
    return disp, liberi, None

@app.route('/', methods=['GET', 'POST'])
def home():
    init_db()
    risultati = None
    errore = None
    
    if request.method == 'POST':
        g = request.form.get('giorno')
        o = request.form.get('ora')
        disp, liberi, errore = trova_sostituti(g, o)
        if not errore:
            risultati = {'disp': disp, 'liberi': liberi, 'giorno': g, 'ora': o}
    
    return render_template_string(HTML_TEMPLATE, r=risultati, e=errore)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Sostituzioni Docenti</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css">
</head>
<body class="container py-5 px-3">
    <h1 class="title has-text-centered">Gestore Sostituzioni</h1>
    {% if e %}<div class="notification is-danger">{{ e }}</div>{% endif %}
    <form method="post" class="box">
        <div class="field">
            <label class="label">Giorno</label>
            <input class="input" type="text" name="giorno" placeholder="es. lunedì" required>
        </div>
        <div class="field">
            <label class="label">Ora (es. 08h10)</label>
            <input class="input" type="text" name="ora" placeholder="es. 08h10" required>
        </div>
        <button class="button is-link is-fullwidth">Cerca Docenti Liberi</button>
    </form>
    {% if r %}
    <div class="box">
        <h2 class="title is-4 has-text-centered">Riepilogo Ricerca</h2>
        <table class="table is-bordered is-striped is-fullwidth">
            <thead><tr><th>Giorno</th><th>Ora</th></tr></thead>
            <tbody><tr><td>{{ r.giorno }}</td><td>{{ r.ora }}</td></tr></tbody>
        </table>
        <article class="message is-success">
            <div class="message-header"><p>In Disposizione (Priorità)</p></div>
            <div class="message-body">
                {% if r.disp %}
                    <ul>{% for d in r.disp %}<li><strong>{{ d }}</strong></li>{% endfor %}</ul>
                {% else %}<p>Nessun docente in disposizione ora.</p>{% endif %}
            </div>
        </article>
        <article class="message is-info">
            <div class="message-header"><p>Altri docenti liberi</p></div>
            <div class="message-body"><p>{{ r.liberi|join(', ') }}</p></div>
        </article>
    </div>
    {% endif %}
</body>
</html>
"""

if __name__ == '__main__':
    app.run(debug=True)