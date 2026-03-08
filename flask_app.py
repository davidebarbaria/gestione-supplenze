import pandas as pd
import sqlite3
from flask import Flask, render_template_string, request, redirect

app = Flask(__name__)
DB_FILE = 'scuola.db'

def get_db():
    conn = sqlite3.connect(DB_FILE)
    # Assicuriamoci che le tabelle esistano come nel tuo progetto originale
    conn.execute('CREATE TABLE IF NOT EXISTS recuperi (docente TEXT PRIMARY KEY, saldo INTEGER DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS registro (id INTEGER PRIMARY KEY AUTOINCREMENT, giorno_lezione TEXT, ora_lezione TEXT, classe TEXT, assente TEXT, sostituto TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS bilancio_ore (docente TEXT PRIMARY KEY, ore_debito INTEGER DEFAULT 0, ore_recuperate INTEGER DEFAULT 0)')
    return conn

@app.route('/', methods=['GET', 'POST'])
def home():
    # Carichiamo i dati dal tuo CSV
    df = pd.read_csv('EXP_COURS.csv', sep=';', dtype=str)
    giorni = sorted(df['GIORNO'].str.strip().dropna().unique().tolist())
    ore = sorted(df['O.INIZIO'].str.strip().dropna().unique().tolist())
    docenti = sorted({d.strip() for d_str in df['DOC_COGN'].dropna() for d in str(d_str).split('#') if d.strip()})
    
    r = None
    errore_copresenza = None

    if request.method == 'POST':
        g, o, a = request.form.get('giorno'), request.form.get('ora'), request.form.get('assente')
        
        # --- NUOVA LOGICA COPRESENZA ---
        # Cerchiamo se nella stessa ora/giorno del docente assente c'è qualcun altro in quella classe
        lezione_assente = df[(df['DOC_COGN'].str.contains(a, na=False)) & (df['GIORNO'].str.strip() == g) & (df['O.INIZIO'] == o)]
        if not lezione_assente.empty:
            classe_target = lezione_assente.iloc[0]['CLASSE']
            # Controlliamo se ci sono altri docenti nella stessa classe/ora
            copresenti = df[(df['CLASSE'] == classe_target) & (df['GIORNO'].str.strip() == g) & (df['O.INIZIO'] == o) & (~df['DOC_COGN'].str.contains(a, na=False))]
            if not copresenti.empty:
                nomi_copr = ", ".join(copresenti['DOC_COGN'].unique())
                errore_copresenza = f"La classe {classe_target} è coperta da {nomi_copr} (Copresenza)."

        # --- TUA LOGICA ORIGINALE DI RICERCA ---
        impegnati = df[(df['GIORNO'].str.strip() == g) & (df['O.INIZIO'] == o)]['DOC_COGN'].unique()
        impegnati_lista = [d.strip() for d_str in impegnati for d in str(d_str).split('#')]
        disp = df[(df['GIORNO'].str.strip() == g) & (df['O.INIZIO'] == o) & (df['MAT_NOME'] == 'DISP')]['DOC_COGN'].unique().tolist()
        liberi = [d for d in docenti if d not in impegnati_lista and d not in disp and d != a]
        r = {'giorno': g, 'ora': o, 'assente': a, 'disp': disp, 'liberi': liberi}

    return render_template_string(HTML_MAIN, giorni=giorni, ore=ore, docenti=docenti, r=r, errore=errore_copresenza)

# Ripristino totale della tua interfaccia con le Tabs
HTML_MAIN = """
<!DOCTYPE html><html><head><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css"></head>
<body class="container p-4">
    <div class="tabs is-toggle is-centered"><ul><li class="is-active"><a>Sostituzione</a></li><li><a href="/giornaliero">Tabellone</a></li><li><a href="/segreteria">Segreteria</a></li></ul></div>
    
    {% if errore %}<div class="notification is-warning is-light">{{ errore }}</div>{% endif %}

    <form method="post" class="box">
        <div class="field is-grouped">
            <div class="select"><select name="giorno">{% for g in giorni %}<option>{{ g }}</option>{% endfor %}</select></div>
            <div class="select"><select name="ora">{% for o in ore %}<option>{{ o }}</option>{% endfor %}</select></div>
            <div class="select"><select name="assente">{% for d in docenti %}<option>{{ d }}</option>{% endfor %}</select></div>
            <button class="button is-link">Trova Sostituto</button>
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

# Le rotte /giornaliero e /segreteria rimangono come nel tuo file originale
@app.route('/segreteria', methods=['GET', 'POST'])
def segreteria():
    conn = get_db()
    if request.method == 'POST':
        conn.execute('INSERT INTO bilancio_ore (docente, ore_debito) VALUES (?, ?) ON CONFLICT(docente) DO UPDATE SET ore_debito = ore_debito + ?', 
                     (request.form.get('docente'), request.form.get('ore'), request.form.get('ore')))
        conn.commit()
    data = conn.execute('SELECT docente, ore_debito, ore_recuperate, (ore_recuperate - ore_debito) as saldo FROM bilancio_ore ORDER BY saldo DESC').fetchall()
    conn.close()
    return render_template_string(HTML_SEGRETERIA, data=data)

HTML_SEGRETERIA = """...""" # Qui va il tuo HTML della segreteria

if __name__ == '__main__':
    app.run(debug=True)
