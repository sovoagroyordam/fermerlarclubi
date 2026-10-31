from aiogram.fsm.state import State, StatesGroup

class CustDevStates(StatesGroup):
    direction = State()          # 1-savol: Chorva / Parranda
    livestock_count = State()    # 1-b: Bosh / Parranda soni
    problem = State()            # 2-savol: Oxirgi muammo
    solution_taken = State()     # 3-savol: Nima qildi, qancha ketdi
    dissatisfaction = State()    # 4-savol: Nima qoniqtirmadi
    phone = State()              # Ixtiyoriy: Telefon raqam
