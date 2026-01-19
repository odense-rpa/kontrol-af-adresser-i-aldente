import mysql.connector


class MySQLClient:
    """MySQL database client with context manager support."""

    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self._connection = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            autocommit=False,
        )
        self._cursor = self._connection.cursor(dictionary=True)

    def __enter__(self):
        """Enter context, returning the object itself."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close the connection gracefully upon context exit."""
        self.close()

    def close(self) -> None:
        """Close the connection gracefully."""
        if self._cursor is not None:
            self._cursor.close()
            self._cursor = None
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def execute_query(self, query: str, params: tuple = ()) -> list:
        """Execute a query and return the results."""
        if not self._connection.is_connected():
            raise RuntimeError("Connection is closed.")

        self._cursor.execute(query, params)
        results = self._cursor.fetchall()
        return results

    def hent_borgere(self) -> list:
        """Hent alle borgere fra databasen."""
        query = """
                SELECT p.cpr as 'Cpr', 
                p.fornavn as 'Fornavn', 
                p.efternavn as 'Efternavn', 
                p.adr1 as 'Adresse', 
                p.postnr as 'Postnummer', 
                p.city as 'By', 
                p.kommune as 'Kommunekode' 
                from patienter p 
                INNER JOIN kommpatient k ON p.cpr = k.cpr 
                WHERE p.inakt = 0 
                AND k.primklinik = 'Specialtandplejen'
                """
        return self.execute_query(query)
