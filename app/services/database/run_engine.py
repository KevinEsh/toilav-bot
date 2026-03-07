# from chatbot_schema import CHATBOT_MODELS
# from dbconfig import create_db_and_tables

if __name__ == "__main__":
    """
    This script initializes the database by creating all necessary tables based on the defined schema.
    It should be run before starting the application to ensure the database is set up correctly.
    """

    from os import environ

    data = environ.get("DATABASE_ENGINE")  # Ensure DATABASE_ENGINE is set in the environment
    print(f"Initializing database at {data}...")
    # create_db_and_tables()
