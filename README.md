# Kontrol af adresser i AlDente

Kontrollerer om borgeres adresser i AlDente (Specialtandplejens journalsystem) er opdaterede ved at sammenligne med autoritative adressedata fra Datafordeler.

## Hvad gør robotten?

1. Henter alle aktive patienter med primklinik `Specialtandplejen` fra AlDente-databasen.
2. Tilføjer hver patient (ekskl. sortlistede CPR-numre) som et arbejdselement i arbejdskøen.
3. For hvert arbejdselement hentes personoplysninger fra Datafordeler via CPR.
4. Kontrollerer om borgeren er registreret som død – rapporteres under gruppen **Død**.
5. Kontrollerer om borgerens kommunekode i AlDente afviger fra kommunekoden i Datafordeler – rapporteres under gruppen **Kommuneskift**.
6. Sammenligner den fulde adresse i AlDente med adressen fra Datafordeler via Levenshtein-afstand.
7. Hvis afstanden er større end 6 rapporteres borgeren under **Ændret adresse**, ellers under **Ingen ændring**.

## Forudsætninger

- Python ≥ 3.13
- [`uv`](https://docs.astral.sh/uv/) til pakkehåndtering
- Adgang til **Automation Server** (arbejdskø)
- Adgang til **AlDente**-databasen (MySQL)
- Adgang til **Datafordeler** inkl. certifikater (`datafordeler.crt` og `datafordeler.key`)

## Installation

```sh
uv sync
```

## Konfiguration

Credentials registreres i Automation Server:
- `AlDente - database`
- `Odense SQL Server` (til odk-tools Tracker)

| Miljøvariabel | Beskrivelse |
|---|---|
| `ATS_URL` | URL til Automation Server API (f.eks. `http://localhost/api`) |
| `ATS_TOKEN` | Adgangstoken til Automation Server |
| `ATS_WORKQUEUE_OVERRIDE` | Overstyrer arbejdskø-ID (bruges til udvikling/test) |
| `CERTIFIKATER` | Sti til mappe med certifikater til Datafordeler-klienten (standard: `/certifikater`) |

## Kørsel

```sh
uv run python main.py --queue   # Fyld arbejdskøen
uv run python main.py           # Behandl arbejdskøen
```

## Afhængigheder

| Pakke | Formål |
|---|---|
| `automation-server-client` | Klient til Automation Server – håndterer arbejdskø og arbejdselementer |
| `datafordeler` | Klient til Datafordeler – henter autoritative personoplysninger og adresser via CPR |
| `levenshtein` | Beregner strengafstand (Levenshtein distance) til sammenligning af adresser |
| `odk-tools` | Sporings- og rapporteringsværktøjer (Tracker og report) |
| `mysql-connector-python` | Forbinder til AlDente MySQL-databasen og henter patientdata |
| `ruff` | Python linter til kodekvalitet |

## GDPR og sikkerhed

Processen behandler CPR-numre, for- og efternavne samt adresser på borgere tilknyttet Specialtandplejen i Odense Kommune. Oplysningerne hentes fra AlDente og Datafordeler under kørsel og gemmes ikke lokalt. Resultater udstilles via `odk-tools report` med rapport-ID `kontrol_af_adresser_i_aldente` og er kun tilgængelige for brugere med adgang til Automation Server.
