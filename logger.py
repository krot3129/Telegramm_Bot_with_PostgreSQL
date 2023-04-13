import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Handler for error and warning logs
error_handler = logging.FileHandler('error.log')
error_handler.setLevel(logging.WARNING)
error_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
error_handler.setFormatter(error_formatter)
logger.addHandler(error_handler)

# Handler for info logs
info_handler = logging.FileHandler('info.log')
info_handler.setLevel(logging.INFO)
info_formatter = logging.Formatter('%(asctime)s - %(message)s')
info_handler.setFormatter(info_formatter)
logger.addHandler(info_handler)

# Handler for console logs
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)