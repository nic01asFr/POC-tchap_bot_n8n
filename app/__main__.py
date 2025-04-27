# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import logging
from bot import main
from config import use_systemd_config

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    use_systemd_config()
    main()
