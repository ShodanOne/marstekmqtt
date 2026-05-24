from dataclasses import dataclass
from typing import Dict

@dataclass
class regdata:
    adr: int
    taille : int
    coef : float
    type : str

MARSTEK_API_SCALER: Dict[str, Dict[str, Dict[str, float]]] = {
    'bat_temp' : {
        'default' : {# Type de batterie = default
            'default' : 1.0 # Version du firmware
        },
        'VenusE 3.0' : {
            '148' : 1.0,
            'default' : 1.0
        }
    },
    'bat_capacity' : {
        'default' : {
            'default' : 1.0
        },
        'VenusE 3.0' : {
            '148' : 1.0,
            'default' : 1.0
        }
    }
}

MARSTEK_REGISTER: Dict[str, Dict[str, Dict[str, regdata]]] = {
    'bat_state' : {
        'default' : { # type de batterie par defaut
            'default' : regdata( # firmware par defaut
                adr=35100,
                taille=1,
                coef=1,
                type='int'
            )
        },
        'VenusE 3.0' : {
            '148' : regdata(
                adr=35100,
                taille=1,
                coef=1,
                type='int'
            ),
            'default' : regdata(
                adr=35100,
                taille=1,
                coef=1,
                type='int'
            )
        }
    },
    'ongrid_power' : {
        'default' : { # type de batterie par defaut
            'default' : regdata( # firmware par defaut
                adr = 30006,
                taille = 1,
                coef = 1,
                type = 'sint'
            )
        },
        'VenusE 3.0' : {
            '148' : regdata(
                adr=30006,
                taille=1,
                coef=1,
                type='sint'
            ),
            'default' : regdata(
                adr=30006,
                taille=1,
                coef=1,
                type='sint'
            )
        }
    },
    'offgrid_power' : {
        'default' : { # type de batterie par defaut
            'default' : regdata( # firmware par defaut
                adr = 32302,
                taille = 1,
                coef = 1,
                type = 'int'
            )
        },
        'VenusE 3.0' : {
            '148' : regdata(
                adr=32302,
                taille=1,
                coef=1,
                type='int'
            ),
            'default' : regdata(
                adr=32302,
                taille=1,
                coef=1,
                type='int'
            )
        }
    },
    'bat_soc' : {
        'default' : { # type de batterie par defaut
            'default' : regdata( # firmware par defaut
                adr = 34002,
                taille = 1,
                coef = 0.1,
                type = 'int'
            )
        },
        'VenusE 3.0' : {
            '148' : regdata(
                adr=34002,
                taille=1,
                coef=0.1,
                type='int'
            ),
            'default' : regdata(
                adr=34002,
                taille=1,
                coef=0.1,
                type='int'
            )
        }
    },
    'bat_temp' : {
        'default' : { # type de batterie par defaut
            'default' : regdata( # firmware par defaut
                adr = 35000,
                taille = 1,
                coef = 0.1,
                type = 'int'
            )
        },
        'VenusE 3.0' : {
            '148' : regdata(
                adr=35000,
                taille=1,
                coef=0.1,
                type='int'
            ),
            'default' : regdata(
                adr=35000,
                taille=1,
                coef=0.1,
                type='int'
            )
        }
    },
    'total_grid_input_energy' : {
        'default' : { # type de batterie par defaut
            'default' : regdata( # firmware par defaut
                adr = 33000,
                taille = 2,
                coef = 10,
                type = 'int'
            )
        },
        'VenusE 3.0' : {
            '148' : regdata(
                adr=33000,
                taille=2,
                coef=10,
                type='int'
            ),
            'default' : regdata(
                adr=33000,
                taille=2,
                coef=10,
                type='int'
            )
        }
    },
    'total_grid_output_energy' : {
        'default' : { # type de batterie par defaut
            'default' : regdata( # firmware par defaut
                adr = 33002,
                taille = 2,
                coef = 10,
                type = 'int'
            )
        },
        'VenusE 3.0' : {
            '148' : regdata(
                adr=33002,
                taille=2,
                coef=10,
                type='int'
            ),
            'default' : regdata(
                adr=33002,
                taille=2,
                coef=10,
                type='int'
            )
        }
    },
    'rated_capacity' : {
        'default' : { # type de batterie par defaut
            'default' : regdata( # firmware par defaut
                adr = 32105,
                taille = 1,
                coef = 1,
                type = 'int'
            )
        },
        'VenusE 3.0' : {
            '148' : regdata(
                adr=32105,
                taille=1,
                coef=1,
                type='int'
            ),
            'default' : regdata(
                adr=32105,
                taille=1,
                coef=1,
                type='int'
            )
        }
    },
    'EMS_version' : {
        'default' : { # type de batterie par defaut
            'default' : regdata( # firmware par defaut
                adr = 30200,
                taille = 1,
                coef = 1,
                type = 'int'
            )
        },
        'VenusE 3.0' : {
            '148' : regdata(
                adr=30200,
                taille=1,
                coef=1,
                type='int'
            ),
            'default' : regdata(
                adr=30200,
                taille=1,
                coef=1,
                type='int'
            )
        }
    }

}