# Metronome

Generatore Python di metronomi **MIDI e WAV** con metro, BPM, durata e pattern ciclici di accentuazione. Utilizza soltanto la libreria standard di Python >= 3.10: nessun modulo aggiuntivo necessario per produrre i file.

Ogni peso del pattern modifica contemporaneamente **dinamica** (velocity MIDI / ampiezza WAV) e **altezza** (nota MIDI / frequenza WAV). Nel WAV i click vengono sintetizzati con un timbro breve, simile a legnetti; non occorrono soundfont.

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

## Parametri

| Opzione | Descrizione | Default |
| --- | --- | --- |
| **--meter N/D** | Metro (denominatore 1, 2, 4, 8, 16 oppure 32) | obbligatorio |
| **--bpm VALORE** | Pulsazioni al minuto dell'unità di tempo | obbligatorio |
| **--bars VALORE** | Durata in battute, anche razionale (es. 3/2 = 1,5 battute) | in alternativa a --seconds |
| **--seconds VALORE** | Durata esatta in secondi | in alternativa a --bars |
| **--pattern "..."** | Lista ciclica di pesi, separati da spazi o virgole | 2 seguito da 1, per una battuta |
| **--tempo-unit FRAZIONE** | Valore di nota cui si riferiscono i BPM | 1/4 |
| **--pitches "..."** | Note MIDI associate ai livelli, crescenti | 72 76 81 84 |
| **--velocities "..."** | Velocity associate ai livelli, crescenti | 48 76 101 124 |
| **--click-ms NUMERO** | Durata del singolo click | 90 |
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

Sono configurati **quattro livelli**. È possibile crearne ulteriori passando sequenze **--pitches** e **--velocities** di uguale lunghezza, con almeno tre elementi e valori strettamente crescenti.

Il pattern **non** viene reimpostato a ogni battuta: ripete ciclicamente i propri pesi, anche quando la sua lunghezza supera quella del metro oppure non coincide con essa. In 4/4, il pattern (2 1 1 1 1 1 1 1) accentua un primo movimento ogni **due** battute. Senza pattern esplicito si usa un accento 2 a ogni inizio battuta, poi 1 per gli altri colpi.

### Relazione tra metro, BPM e battiti

Si produce **un click per ogni unità del denominatore**: quattro click in 4/4, sei in 6/8, cinque in 5/16, ecc.

I BPM si riferiscono alla **semiminima per impostazione predefinita**, indipendentemente dal metro. Per esempio, in 6/8, se si vogliono 72 semiminime puntate al minuto, impostare **--tempo-unit 3/8**. Anche **--tempo-unit 1/8** è supportato.

Il file WAV dura esattamente quanto richiesto, salvo l'arrotondamento a un campione. Se l'ultima percussione eccede la durata, viene troncata. Analogamente, la traccia MIDI termina alla durata prevista, con la risoluzione di 960 tick per semiminima e l'approssimazione del tempo MIDI.

## Esempi

**4/4, un accento ogni due misure:**

~~~bash
python -m metronome --meter 4/4 --bpm 120 --bars 8 \
  --pattern "(2 1 1 1 1 1 1 1)" --output output/two-bars
~~~

**3/4, tre livelli di accentuazione:**

~~~bash
python -m metronome --meter 3/4 --bpm 90 --bars 6 \
  --pattern "2 0 1 1 0 1" --output output/three-levels
~~~

**6/8, pulsazione di semiminima puntata e durata di 30 secondi:**

~~~bash
python -m metronome --meter 6/8 --bpm 72 --tempo-unit 3/8 \
  --seconds 30 --pattern "3 1 1 2 1 1" --output output/six-eight
~~~

**Cinque livelli di accentuazione personalizzati:**

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
~~~

Un'unica sequenza di eventi genera entrambi i formati, in modo che la struttura degli accenti sia identica. Il WAV viene prodotto per blocchi senza tenere tutta la traccia in RAM.

**MIDI:** Standard MIDI File formato 0, metadati di tempo e metro, canale 1 e programma 116 General MIDI (Woodblock, program change 115 con indice zero-based). La note on MIDI ha altezza e velocity variabili. La resa timbrica MIDI dipende dal sintetizzatore. Non si usa il canale 10 delle percussioni, nel quale diverse note corrispondono a strumenti diversi.

**WAV:** PCM mono, 16 bit, con sintesi deterministica interna di risonanze inarmoniche e attacco rumoroso.

## Test

~~~bash
python -m unittest discover -s tests -v
~~~

## Licenza

GPL-3.0, come nel file LICENSE.
