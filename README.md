# Metronome

Generatore Python di metronomi **MIDI e WAV** con metro, BPM, durata e pattern ciclici di accentuazione. Utilizza soltanto la libreria standard di Python >= 3.10: nessun modulo aggiuntivo necessario per produrre i file.

Sono disponibili due modalità: **click** (default), con legnetti sintetizzati, e **percussion**, con cassa e tom medio-gravi campionati da Freesound e inclusi nel pacchetto. Non occorrono soundfont, connessione o credenziali Freesound per generare i file.

In modalità click ogni peso del pattern modifica contemporaneamente **dinamica** (velocity MIDI / ampiezza WAV) e **altezza** (nota MIDI / frequenza WAV). In modalità percussion modifica la **dinamica**, mentre gli strumenti seguono il metro.

## Uso immediato

Dalla cartella del repository:

~~~bash
python -m metronome --meter 4/4 --bpm 120 --bars 8 \
  --pattern "(2 1 1 1 1 1 1 1)" --output output/alternate-bars
~~~

Crea i due file output/alternate-bars.mid e output/alternate-bars.wav.

Facoltativamente, installazione del comando da terminale:

~~~bash
python -m pip install -e .
metronome --meter 3/4 --bpm 96 --bars 4 --output output/three-four
~~~

### Windows (PowerShell e Prompt dei comandi)

Richiede Python 3.10 o successivo. Dalla cartella del repository:

~~~powershell
py -3 -m pip install .
py -3 -m metronome --mode percussion --meter 4/4 --bpm 110 --bars 2 --subdivision 2 --pattern "3 0 1 0 2 0 1 0" --output "output\prova percussioni"
~~~

L'installazione include i campioni Freesound e il comando `metronome`. Sono supportati percorsi con spazi e caratteri Unicode. Non occorrono FFmpeg o dipendenze audio esterne.

Gli esempi multilinea seguenti usano la continuazione `\` di Bash/zsh: in PowerShell o nel Prompt dei comandi unisci le righe in un unico comando, sostituendo `python` con `py -3` se necessario.

## Parametri

| Opzione | Descrizione | Default |
| --- | --- | --- |
| **--meter N/D** | Metro (denominatore 1, 2, 4, 8, 16 oppure 32) | obbligatorio |
| **--bpm VALORE** | Pulsazioni al minuto dell'unità di tempo | obbligatorio |
| **--mode** | click oppure percussion | click |
| **--subdivision N** | Colpi per unità del denominatore, da 1 a 32 | 1 |
| **--bars VALORE** | Durata in battute, anche razionale (es. 3/2 = 1,5 battute) | in alternativa a --seconds |
| **--seconds VALORE** | Durata esatta in secondi | in alternativa a --bars |
| **--pattern "..."** | Lista ciclica di pesi, separati da spazi o virgole | 2 seguito da 1, per una battuta |
| **--tempo-unit FRAZIONE** | Valore di nota cui si riferiscono i BPM | 1/4 |
| **--pitches "..."** | Note MIDI associate ai livelli, crescenti; solo modalità click | 72 76 81 84 |
| **--velocities "..."** | Velocity associate ai livelli, crescenti | 48 76 101 124 |
| **--click-ms NUMERO** | Durata del click WAV e delle note MIDI; i campioni percussion WAV conservano la propria coda | 90 |
| **--sample-rate NUMERO** | Campionamento del WAV, in Hz | 44100 |
| **--format** | midi, wav, both | both |
| **--output PERCORSO** | Prefisso dei nomi di output | metronome |

Le due opzioni **--bars** e **--seconds** sono mutualmente esclusive; occorre specificarne esattamente una.

## Livelli di accentuazione

| Peso | Altezza MIDI | Velocity | Ruolo |
| --- | ---: | ---: | --- |
| 0 | 72 (Do5) | 48 | Debole |
| 1 | 76 (Mi5) | 76 | Ordinario |
| 2 | 81 (La5) | 101 | Forte |
| 3 | 84 (Do6) | 124 | Fortissimo |

Sono configurati **quattro livelli**. È possibile crearne ulteriori passando sequenze **--pitches** e **--velocities** di uguale lunghezza, con almeno tre elementi e valori strettamente crescenti. In modalità percussion basta personalizzare **--velocities**, perché le note identificano gli strumenti General MIDI. Il livello 0 è un colpo debole, non una pausa.

Il pattern **non** viene reimpostato a ogni battuta: ripete ciclicamente i propri pesi, anche quando la sua lunghezza supera quella del metro oppure non coincide con essa. In 4/4, il pattern (2 1 1 1 1 1 1 1) accentua un primo movimento ogni **due** battute. Senza pattern esplicito si usa un accento 2 a ogni inizio battuta, poi 1 per gli altri colpi.

### Relazione tra metro, BPM e battiti

Per default si produce **un colpo per ogni unità del denominatore**: quattro in 4/4, sei in 6/8, cinque in 5/16, ecc. **--subdivision N** divide ciascuna unità in N parti uguali: in 4/4, N=2 produce otto crome, N=3 dodici crome di terzina, N=4 sedici semicrome. La lista **--pattern** assegna un peso a ogni colpo della griglia, senza cambiare metro, BPM o durata.

I BPM si riferiscono alla **semiminima per impostazione predefinita**, indipendentemente dal metro. Per esempio, in 6/8, se si vogliono 72 semiminime puntate al minuto, impostare **--tempo-unit 3/8**. Anche **--tempo-unit 1/8** è supportato.

Il file WAV dura esattamente quanto richiesto, salvo l'arrotondamento a un campione. Se l'ultima percussione eccede la durata, viene troncata. Analogamente, la traccia MIDI termina alla durata prevista, con la risoluzione di 960 tick per semiminima e l'approssimazione del tempo MIDI.

### Beat di percussioni medio-gravi

~~~bash
python -m metronome --mode percussion --meter 4/4 --bpm 110 --bars 8 \
  --subdivision 2 --pattern "3 0 1 0 2 0 1 0" \
  --output output/percussion-four-four
~~~

La cassa segna l'inizio della battuta, il tom grave gli inizi dei gruppi successivi, il tom medio gli altri colpi e le suddivisioni interne. L'orchestrazione ricomincia a ogni battuta, mentre il pattern di pesi continua ciclicamente anche oltre la stanghetta. Con un pattern esplicito non vengono aggiunti accenti dinamici automatici.

I metri composti con denominatore almeno 8 e numeratore multiplo di 3 si raggruppano in tre (6/8 = 3+3, 9/8 = 3+3+3); i metri pari semplici in due (4/4 = 2+2); i metri dispari superiori a tre in 3 seguito da gruppi di 2 (5/8 = 3+2, 7/8 = 3+2+2). Nei metri di tre unità il gruppo è unico.

**7/8, due suddivisioni per croma:**

~~~bash
python -m metronome --mode percussion --meter 7/8 --bpm 90 --bars 4 \
  --subdivision 2 --pattern "3 0 1 0 1 0 2 0 1 0 2 0 1 0" \
  --output output/percussion-seven-eight
~~~

I WAV utilizzano tre campioni CC0: [kick.wav di KEVOY](https://freesound.org/people/KEVOY/sounds/82309/), [Low Tom di johnnydekk](https://freesound.org/people/johnnydekk/sounds/581467/) e [TOM_MID_natural_1.wav di jannevse](https://freesound.org/people/jannevse/sounds/614411/). Provenienza, trasformazioni e checksum sono in [metronome/samples/sources.json](metronome/samples/sources.json); i crediti sono in [metronome/samples/README.md](metronome/samples/README.md). Le code dei campioni si sovrappongono e sono limitate alla durata complessiva richiesta.

## Esempi con audio

Tre dimostrazioni brevi sono incluse nella cartella [demos](demos/). Ogni comando rigenera il WAV collegato.

**1. Click in 4/4, un accento ogni due misure — 4 secondi.**

[Ascolta il WAV: click in 4/4](demos/click-4-4.wav)

~~~bash
python -m metronome --mode click --meter 4/4 --bpm 120 --bars 2 \
  --pattern "2 1 1 1 1 1 1 1" --format wav --output demos/click-4-4
~~~

**2. Percussioni in 6/8, pulsazione di semiminima puntata — circa 3,33 secondi.**

[Ascolta il WAV: percussioni in 6/8](demos/percussion-6-8.wav)

~~~bash
python -m metronome --mode percussion --meter 6/8 --bpm 72 --tempo-unit 3/8 \
  --bars 2 --pattern "3 1 0 2 1 0" \
  --format wav --output demos/percussion-6-8
~~~

**3. Percussioni in 7/8 (3+2+2), due suddivisioni per croma — circa 4,67 secondi.**

[Ascolta il WAV: percussioni in 7/8](demos/percussion-7-8.wav)

~~~bash
python -m metronome --mode percussion --meter 7/8 --bpm 90 --bars 2 \
  --subdivision 2 --pattern "3 0 1 0 1 0 2 0 1 0 2 0 1 0" \
  --format wav --output demos/percussion-7-8
~~~

### Livelli personalizzati

**Cinque livelli di accentuazione, con esportazione MIDI:**

~~~bash
python -m metronome --meter 4/4 --bpm 110 --bars 3 \
  --pattern "4 1 2 0 3 1 2 0" \
  --pitches "60 64 67 72 76" \
  --velocities "35 55 75 98 124" \
  --format midi --output output/custom
~~~

## API Python

~~~python
from metronome import generate_track, write_midi, write_wav

track = generate_track(
    meter="4/4",
    bpm=120,
    bars="3/2",
    pattern=(2, 1, 1, 1, 1, 1, 1, 1),
)

write_midi("example.mid", track)
write_wav("example.wav", track)

beat = generate_track(
    mode="percussion", meter="7/8", bpm=90, bars=4,
    subdivision=2, pattern="3 0 1 0 1 0 2 0 1 0 2 0 1 0",
)
write_midi("beat.mid", beat)
write_wav("beat.wav", beat)
~~~

Un'unica sequenza di eventi genera entrambi i formati, in modo che la struttura degli accenti sia identica. Il WAV viene prodotto per blocchi senza tenere tutta la traccia in RAM.

**MIDI:** Standard MIDI File formato 0, metadati di tempo e metro. Modalità click: canale 1 e programma 116 General MIDI (Woodblock, program change 115 con indice zero-based), con altezza e velocity variabili. Modalità percussion: canale 10, note 36 (Bass Drum 1), 45 (Low Tom), 47 (Low-Mid Tom), velocity secondo il pattern. I campioni Freesound sono usati nel WAV; il timbro MIDI dipende dal kit del sintetizzatore.

**WAV:** PCM mono, 16 bit, con sintesi deterministica interna in modalità click e campioni Freesound in modalità percussion. I campioni sono ricampionati alla frequenza richiesta usando la libreria standard.

## Test

~~~bash
python -m unittest discover -s tests -v
~~~

Il workflow [Package compatibility](.github/workflows/tests.yml) verifica Windows con Python 3.10–3.14, oltre a Linux e macOS con Python 3.10 e 3.14. Ogni job costruisce sdist e wheel, installa il wheel senza dipendenze in un ambiente pulito ed esegue i test fuori dal checkout, inclusi esportazioni MIDI/WAV, campioni inclusi, percorsi Unicode, output reindirizzato e comando installato.

Per eseguire lo stesso controllo di packaging localmente:

~~~bash
python -m pip install build
python scripts/check_package.py
~~~

## Licenza

Codice GPL-3.0, come nel file LICENSE. I tre campioni audio inclusi restano CC0-1.0, come documentato nei rispettivi crediti.
