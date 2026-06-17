import logging
from utils.helpers import ensure_directory

ensure_directory("output/logs")

logging.basicConfig(
    filename="output/logs/app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)
