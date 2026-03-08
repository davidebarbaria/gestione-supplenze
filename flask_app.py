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

def init_db():
    conn = get_db()
    # Tabella per i debiti orari (Assenze)
    conn.execute('CREATE TABLE IF NOT EXISTS bilancio_ore (docente TEXT PRIMARY KEY, ore_debito INTEGER DEFAULT 0, ore_recuperate INTEGER DEFAULT 0)')
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def home():
    init_db()
    r = None
    errore = None
    
    if request.method == 'POST':
        g = request.form.get('giorno')
        o = request.form.get('ora')
        classe_input = request.form.get('classe', '').strip().upper()
        
        if not os.path.exists(CSV_FILE):
            return "Errore: File CSV non trovato!"
        
        df = pd.read_csv(CSV_FILE, sep=';', dtype=str)
        df['DOC_COGN'] = df['DOC_COGN'].fillna('').str.strip()
        
        # 1. LOGICA COPRESENZA (Se inserisci la classe)
        if classe_input:
            lezione = df[(df['CLASSE'] == classe_input) & (df['GIORNO'].str.lower() == g.lower()) & (df['O.INIZIO'] == o)]
            if len(lezione) > 1:
                docenti_copr = [d for d_str in lezione['DOC_COGN'] for d in d_str.split('#') if d.strip()]
                errore = f"La classe {classe_input} è già coperta da: {', '.join(set(docenti_copr))}"

        # 2. LOGICA RICERCA (La tua originale con messaggi colorati)
        disp = df[(df['GIORNO'].str.lower() == g.lower()) & (df['O.INIZIO'] == o) & (df['MAT_NOME'] == 'DISP')]['DOC_COGN'].unique().tolist()
        impegnati = df[(df['GIORNO'].str.lower() == g.lower()) & (df['O.INIZIO'] == o)]['DOC_COGN'].unique()
        impegnati_lista = [d for d_str in impegnati for d in str(d_str).split('#') if d.strip()]
        
        tutti = sorted({d for d_str in df['DOC_COGN'].dropna() for d in str(d_str).split('#') if d.strip()})
        liberi = [d for d in tutti if d not in impegnati_lista and d not in disp]
        
        r = {'giorno': g, 'ora': o, 'disp': disp, 'liberi': liberi}

    return render_template_string(HTML_TEMPLATE, r=r, errore=errore)

@app.route('/segna_assenza', methods=['POST'])
def segna_assenza():
    docente = request.form.get('docente')
    ore = request.form.get('ore', 0)
    if docente and ore:
        conn = get_db()
        conn.execute('''INSERT INTO bilancio_ore (docente, ore_debito) VALUES (?, ?) 
                        ON CONFLICT(docente) DO UPDATE SET ore_debito = ore_debito + ?''', 
                     (docente, ore, ore))
        conn.commit()
        conn.close()
    return redirect('/')

# --- LA TUA INTERFACCIA ORIGINALE RIPRISTINATA ---
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
    
    {% if errore %}<div class="notification is-warning">{{ errore }}</div>{% endif %}

    <div class="columns">
        <div class="column">
            <form method="post" class="box">
                <h3 class="subtitle">Cerca Sostituto</h3>
                <div class="field"><label class="label">Giorno</label><input class="input" type="text" name="giorno" placeholder="es. lunedì" required></div>
                <div class="field"><label class="label">Ora</label><input class="input" type="text" name="ora" placeholder="es. 08h10" required></div>
                <div class="field"><label class="label">Classe (per copresenza)</label><input class="input" type="text" name="classe" placeholder="es. 1H"></div>
                <button class="button is-link is-fullwidth">Cerca</button>
            </form>
        </div>
        <div class="column">
            <form action="/segna_assenza" method="post" class="box">
                <h3 class="subtitle">Segna Assenza (Debito)</h3>
                <div class="field"><label class="label">Docente</label><input class="input" type="text" name="docente" required></div>
                <div class="field"><label class="label">Ore di assenza</label><input class="input" type="number" name="ore" required></div>
                <button class="button is-danger is-fullwidth">Registra Debito</button>
            </form>
        </div>
    </div>

    {% if r %}
    <div class="box">
        <h2 class="subtitle">Risultati per {{ r.giorno }} alle {{ r.ora }}</h2>
        <article class="message is-success">
            <div class="message-header"><p>In Disposizione (Priorità)</p></div>
            <div class="message-body">
                {% if r.disp %}<ul>{% for d in r.disp %}<li><strong>{{ d }}</strong></li>{% endfor %}</ul>
                {% else %}<p>Nessuno in disposizione.</p>{% endif %}
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
