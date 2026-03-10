import pandas as pd
import sqlite3
from flask import Flask, render_template_string, request, redirect

app = Flask(__name__)
DB_FILE = 'scuola.db'

def get_db():
    conn = sqlite3.connect(DB_FILE)
    # Assicuriamoci che le tabelle esistano
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

        # 1. LOGICA COPRESENZE: Cerchiamo la lezione del docente assente
        lezione = df[(df['GIORNO'] == g) & (df['O.INIZIO'] == o) & (df['DOC_COGN'].str.contains(a, na=False))]
        
        if not lezione.empty:
            classe_target = lezione.iloc[0]['CLASSE']
            docenti_ora = lezione.iloc[0]['DOC_COGN']
            
            # Verifichiamo se ci sono più nomi (separati da # nel CSV)
            lista_docenti = [d.strip() for d in docenti_ora.split('#')]
            if len(lista_docenti) > 1:
                altri = [d for d in lista_docenti if d != a]
                avviso_copresenza = f"ATTENZIONE: In classe {classe_target} è presente il co-docente: {', '.join(altri)}. Sostituzione non strettamente necessaria."

            # 2. CERCA SOSTITUTI (Docenti che hanno 'DISP' o 'Z_...' in quell'ora)
            sostituti = df[(df['GIORNO'] == g) & (df['O.INIZIO'] == o) & (df['MAT_NOME'].str.contains('DISP|Z_', na=False, case=False))]
            lista_sostituti = sostituti['DOC_COGN'].unique().tolist()
            
            risultato = {
                'classe': classe_target,
                'sostituti': lista_sostituti,
                'assente': a
            }

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css">
        <title>Gestione Supplenze</title>
    </head>
    <body class="container p-4">
        <div class="tabs is-toggle is-centered">
            <ul>
                <li class="is-active"><a href="/">Sostituzione</a></li>
                <li><a href="/segreteria">Segreteria</a></li>
            </ul>
        </div>
        
        <form method="post" class="box">
            <div class="columns">
                <div class="column"><label>Giorno</label>
                    <div class="select is-fullwidth"><select name="giorno">
                        {% for g in giorni %}<option>{{ g }}</option>{% endfor %}
                    </select></div>
                </div>
                <div class="column"><label>Ora</label>
                    <div class="select is-fullwidth"><select name="ora">
                        {% for o in ore %}<option>{{ o }}</option>{% endfor %}
                    </select></div>
                </div>
                <div class="column"><label>Docente Assente</label>
                    <input type="text" name="docente_assente" class="input" placeholder="Cognome..." required>
                </div>
            </div>
            <button class="button is-link is-fullwidth">Cerca Sostituto</button>
        </form>

        {% if avviso_copresenza %}
            <div class="notification is-warning">{{ avviso_copresenza }}</div>
        {% endif %}

        {% if risultato %}
            <div class="box">
                <h3 class="title is-4">Risultati per Classe {{ risultato.classe }}</h3>
                <ul>
                {% for s in risultato.sostituti %}
                    <li class="mb-2">{{ s }} 
                        <form method="post" action="/conferma" style="display:inline">
                            <input type="hidden" name="assente" value="{{ risultato.assente }}">
                            <input type="hidden" name="sostituto" value="{{ s }}">
                            <button class="button is-small is-success">Assegna</button>
                        </form>
                    </li>
                {% endfor %}
                </ul>
            </div>
        {% endif %}
    </body>
    </html>
    """, giorni=giorni, ore=ore, risultato=risultato, avviso_copresenza=avviso_copresenza)

@app.route('/segreteria', methods=['GET', 'POST'])
def segreteria():
    # Carichiamo i docenti dal CSV per il menù a tendina
    df = pd.read_csv('EXP_COURS.csv', sep=';', dtype=str)
    lista_completa_docenti = sorted({d.strip() for d_str in df['DOC_COGN'].dropna() for d in str(d_str).split('#') if d.strip()})
    
    conn = get_db()
    if request.method == 'POST':
        docente = request.form.get('docente')
        ore = int(request.form.get('ore'))
        conn.execute('INSERT INTO bilancio_ore (docente, ore_debito) VALUES (?, ?) ON CONFLICT(docente) DO UPDATE SET ore_debito = ore_debito + ?', (docente, ore, ore))
        conn.commit()
    
    dati = conn.execute('SELECT docente, ore_debito, ore_recuperate, (ore_recuperate - ore_debito) as saldo FROM bilancio_ore ORDER BY saldo ASC').fetchall()
    conn.close()

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css"></head>
    <body class="container p-4">
        <div class="tabs is-toggle is-centered">
            <ul>
                <li><a href="/">Sostituzione</a></li>
                <li class="is-active"><a>Segreteria</a></li>
            </ul>
        </div>
        <form method="post" class="box">
            <h3 class="subtitle">Aggiungi Debito Orario (Permesso)</h3>
            <div class="field has-addons">
                <div class="control is-expanded">
                    <div class="select is-fullwidth">
                        <select name="docente" required>
                            <option value="">Seleziona Docente...</option>
                            {% for d in docenti %}<option value="{{ d }}">{{ d }}</option>{% endfor %}
                        </select>
                    </div>
                </div>
                <div class="control">
                    <input type="number" name="ore" class="input" placeholder="Ore" required>
                </div>
                <div class="control">
                    <button class="button is-danger">Aggiungi Debito</button>
                </div>
            </div>
        </form>

        <table class="table is-fullwidth is-striped">
            <thead><tr><th>Docente</th><th>Debito</th><th>Recuperate</th><th>Saldo (Netto)</th></tr></thead>
            <tbody>
                {% for d in dati %}
                <tr>
                    <td>{{ d[0] }}</td><td>{{ d[1] }}</td><td>{{ d[2] }}</td>
                    <td class="{% if d[3] < 0 %}has-text-danger{% else %}has-text-success{% endif %}"><b>{{ d[3] }}</b></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </body>
    </html>
    """, docenti=lista_completa_docenti, dati=dati)

if __name__ == '__main__':
    app.run(debug=True)
