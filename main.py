import asyncio
import logging
import sys
import os
import Levenshtein

from automation_server_client import (
    AutomationServer,
    Workqueue,
    WorkItemError,
    Credential,
    WorkItemStatus,
)
from datafordeler import Datafordeler as DatafordelerClient
from odk_tools.tracking import Tracker
from odk_tools.reporting import report
from process.mysql_client import MySQLClient

datafordeler: DatafordelerClient
mysql_client: MySQLClient
tracker: Tracker

proces_navn = "Kontrol af adresser i AlDente"


def normaliser_adresse(addr):
    return (
        addr.lower().replace(" ", "").replace(",", "").replace(".", "").replace("-", "")
    )


async def populate_queue(workqueue: Workqueue):
    blacklist_cpr = [
        "000000-0000",
        "010101-0102",
        "010101-0101",
        "999999-9999"        
    ]

    borgere = mysql_client.hent_borgere()

    for borger in borgere:
        if borger["Cpr"] in blacklist_cpr:
            continue

        workqueue.add_item(data=borger, reference=f"{borger['Cpr']}")


async def process_workqueue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    for item in workqueue:
        with item:
            data = item.data  # Item data deserialized from json as dict

            try:
                person_oplysninger = datafordeler.hent_personoplysninger(
                    cpr=str(data["Cpr"]).replace("-", "")
                )

                # Kontroller om borger er død
                if person_oplysninger.get("Person").get("status") == "doed":
                    report(
                        report_id="kontrol_af_adresser_i_aldente",
                        group="Død",
                        json={
                            "Cpr": data["Cpr"],
                            "Navn": f"{data.get('Fornavn', '')} {data.get('Efternavn', '')}",
                            "Adresse i AlDente": f"{data.get('Adresse', '')}, {data.get('Postnummer', '')} {data.get('By', '')} ({data.get('Kommunekode', '')})",
                            "Adresse i stamdata": "",
                        },
                    )
                    tracker.track_partial_task(proces_navn)
                    continue

                aktiv_adresse = datafordeler.hent_aktiv_adresse(
                    cpr=str(data["Cpr"]).replace("-", "")
                )
                formateret_adresse = datafordeler.formater_adresse(
                    aktiv_adresse.get("Adresseoplysninger", {})
                )
                formateret_adresse_norm = normaliser_adresse(formateret_adresse)

                # Kontroller kommuneskift
                if aktiv_adresse.get("Adresseoplysninger", {}).get(
                    "CprAdresse", {}
                ).get("cprKommunekode").lstrip("0") != data.get("Kommunekode"):
                    report(
                        report_id="kontrol_af_adresser_i_aldente",
                        group="Kommuneskift",
                        json={
                            "Cpr": data["Cpr"],
                            "Navn": f"{data.get('Fornavn', '')} {data.get('Efternavn', '')}",
                            "Adresse i AlDente": f"{data.get('Adresse', '')}, {data.get('Postnummer', '')} {data.get('By', '')} ({data.get('Kommunekode', '')})",
                            "Adresse i stamdata": f"{formateret_adresse} ({aktiv_adresse.get('Adresseoplysninger', {}).get('CprAdresse', {}).get('cprKommunekode')})",
                        },
                    )
                    tracker.track_task(proces_navn)
                    continue

                aldente_adresse = f"{data.get('Adresse', '')}, {data.get('Postnummer', '')} {data.get('By', '')}"
                aldente_adresse_norm = normaliser_adresse(aldente_adresse)

                # Kontroller adresseændring
                diff = Levenshtein.distance(
                    aldente_adresse_norm, formateret_adresse_norm
                )
                if diff > 6:
                    report(
                        report_id="kontrol_af_adresser_i_aldente",
                        group="Ændret adresse",
                        json={
                            "Cpr": data["Cpr"],
                            "Navn": f"{data.get('Fornavn', '')} {data.get('Efternavn', '')}",
                            "Adresse i AlDente": f"{data.get('Adresse', '')}, {data.get('Postnummer', '')} {data.get('By', '')} ({data.get('Kommunekode', '')})",
                            "Adresse i stamdata": f"{formateret_adresse} ({aktiv_adresse.get('Adresseoplysninger', {}).get('CprAdresse', {}).get('cprKommunekode')})",
                        },
                    )
                    tracker.track_task(proces_navn)
                else:
                    report(
                        report_id="kontrol_af_adresser_i_aldente",
                        group="Ingen ændring",
                        json={
                            "Cpr": data["Cpr"],
                            "Navn": f"{data.get('Fornavn', '')} {data.get('Efternavn', '')}",
                            "Adresse i AlDente": f"{data.get('Adresse', '')}, {data.get('Postnummer', '')} {data.get('By', '')} ({data.get('Kommunekode', '')})",
                            "Adresse i stamdata": f"{formateret_adresse} ({aktiv_adresse.get('Adresseoplysninger', {}).get('CprAdresse', {}).get('cprKommunekode')})",
                        },
                    )
                    tracker.track_partial_task(proces_navn)

            except WorkItemError as e:
                # A WorkItemError represents a soft error that indicates the item should be passed to manual processing or a business logic fault
                logger.error(f"Error processing item: {data}. Error: {e}")
                item.fail(str(e))


if __name__ == "__main__":
    ats = AutomationServer.from_environment()
    workqueue = ats.workqueue()

    aldente_credential = Credential.get_credential("AlDente - database")
    tracking_credential = Credential.get_credential("Odense SQL Server")

    tracker = Tracker(
        username=tracking_credential.username, password=tracking_credential.password
    )

    # Initialize MySQL client
    mysql_client = MySQLClient(
        host=aldente_credential.data["server"],  # Assuming username contains host
        port=aldente_credential.data["port"],
        user=aldente_credential.username,
        password=aldente_credential.password,
        database=aldente_credential.data["database"],
    )

    # Overskriv stien i forbindelse med udvikling
    certifikat_sti = os.getenv("CERTIFIKATER", "/certifikater")
    datafordeler = DatafordelerClient(
        certifikat_sti=os.path.join(certifikat_sti, "datafordeler.crt"),
        certifikat_nøglefil=os.path.join(certifikat_sti, "datafordeler.key"),
    )

    # Queue management
    if "--queue" in sys.argv:
        workqueue.clear_workqueue(WorkItemStatus.NEW)
        asyncio.run(populate_queue(workqueue))
        exit(0)

    # Process workqueue
    asyncio.run(process_workqueue(workqueue))
