from dotenv import load_dotenv
load_dotenv()

from validator.pipeline import run_pipeline
from reports.daily_report import generate_daily_report
from reports.metrics import generate_metrics
from db.indexes import create_indexes


def print_classification_counts():

    metrics = generate_metrics()
    print("\nClassification counts")
    print("---------------------")
    print(f"GOOD data    : {metrics.get('good_data', 0)}")
    print(f"Human review : {metrics.get('human_review', 0)}")
    print(f"Rejected     : {metrics.get('rejected', 0)}")
    print(f"Total records: {metrics.get('total_records', 0)}")

if __name__ == "__main__":

    try:
        create_indexes()

        run_pipeline()

        generate_daily_report()
        print_classification_counts()
    finally:
        from db.mongo import client
        client.close()

    print("Validation pipeline completed")
