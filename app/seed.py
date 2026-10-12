"""Демо данни: 3 учители, 15 ученици в 3 класа, примерни тестове и задания."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .curricula import load_curricula_from_disk
from .models import (
    Assignment,
    AssignmentClassroom,
    Classroom,
    ClassroomStudent,
    Curriculum,
    Question,
    Test,
    User,
    utcnow,
)
from .question_types import normalize_data

TEACHERS = [
    ("m.ivanova", "Мария Иванова", "Математика", "#2563eb"),
    ("g.petrov", "Георги Петров", "История и цивилизации", "#d97706"),
    ("e.nikolova", "Елена Николова", "Български език и литература", "#db2777"),
]

STUDENTS = {
    "7а": ["Александър Димитров", "Виктория Стоянова", "Даниел Колев", "Ива Георгиева", "Калоян Тодоров"],
    "8б": ["Мартин Петков", "Никол Христова", "Петър Василев", "Радостина Маринова", "Стефан Илиев"],
    "12в": ["Теодора Ангелова", "Христо Попов", "Яна Костадинова", "Борис Найденов", "Габриела Михайлова"],
}

COLORS = ["#0ea5e9", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444", "#14b8a6", "#6366f1", "#ec4899"]

_TRANSLIT = str.maketrans(
    "абвгдежзийклмнопрстуфхцчшщъьюя",
    "abvgdejziyklmnoprstufhcc~~~~~~",
)


def _username(full_name: str) -> str:
    first, last = full_name.split()[0], full_name.split()[-1]
    mapping = {
        "ж": "zh",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sht",
        "ъ": "a",
        "ь": "y",
        "ю": "yu",
        "я": "ya",
        "й": "y",
    }

    def tr(s: str) -> str:
        out = []
        for ch in s.lower():
            if ch in mapping:
                out.append(mapping[ch])
            else:
                out.append(ch.translate(_TRANSLIT))
        return "".join(out)

    return f"{tr(first)[0]}.{tr(last)}"


def _q(qtype: str, stem: str, data: dict, *, difficulty: int = 2, points: float = 1, topic: str = "") -> dict:
    return {
        "type": qtype,
        "stem": stem,
        "data": normalize_data(qtype, data),
        "difficulty": difficulty,
        "points": points,
        "topic": topic,
    }


def math_questions() -> list[dict]:
    return [
        _q(
            "single_choice",
            '<p>Решете уравнението <span class="ql-formula" data-value="x^2-5x+6=0">x^2-5x+6=0</span>. Кои са корените му?</p>',
            {
                "options": [
                    {"id": "a", "text": "$x_1=2,\\ x_2=3$"},
                    {"id": "b", "text": "$x_1=-2,\\ x_2=-3$"},
                    {"id": "c", "text": "$x_1=1,\\ x_2=6$"},
                    {"id": "d", "text": "$x_1=-1,\\ x_2=-6$"},
                ],
                "correct": "a",
            },
            topic="5. Квадратни уравнения",
        ),
        _q(
            "numeric",
            '<p>Пресметнете дискриминантата на уравнението <span class="ql-formula" data-value="2x^2-3x-5=0">2x^2-3x-5=0</span>.</p>',
            {"answer": 49, "tolerance": 0, "unit": "", "widget": "input"},
            topic="5. Квадратни уравнения",
        ),
        _q(
            "multi_choice",
            "<p>Кои от посочените числа са ирационални?</p>",
            {
                "options": [
                    {"id": "a", "text": "$\\sqrt{2}$"},
                    {"id": "b", "text": "$\\sqrt{9}$"},
                    {"id": "c", "text": "$\\pi$"},
                    {"id": "d", "text": "$0{,}75$"},
                    {"id": "e", "text": "$\\sqrt{5}$"},
                ],
                "correct": ["a", "c", "e"],
            },
            difficulty=2,
            points=2,
            topic="4. Квадратен корен",
        ),
        _q(
            "true_false",
            "<p>Преценете верността на твърденията за окръжност.</p>",
            {
                "statements": [
                    {
                        "id": "s1",
                        "text": "Вписан ъгъл е равен на половината от централния ъгъл над същата дъга.",
                        "answer": True,
                    },
                    {
                        "id": "s2",
                        "text": "Допирателната към окръжност е перпендикулярна на радиуса в допирната точка.",
                        "answer": True,
                    },
                    {
                        "id": "s3",
                        "text": "Две концентрични окръжности винаги имат обща точка.",
                        "answer": False,
                    },
                    {
                        "id": "s4",
                        "text": "Диаметър, перпендикулярен на хорда, я разполовява.",
                        "answer": True,
                    },
                ]
            },
            points=2,
            topic="6. Окръжност",
        ),
        _q(
            "fill_blank",
            "<p>Попълнете пропуснатите числа.</p>",
            {
                "text": "Пермутациите без повторение от 4 елемента са [[1]] на брой, а комбинациите от 5 елемента 2-ри клас – [[2]].",
                "blanks": {"1": {"answers": ["24"]}, "2": {"answers": ["10"]}},
            },
            points=2,
            topic="1. Основни комбинаторни понятия",
        ),
        _q(
            "matching",
            "<p>Свържете всяко понятие със съответното му определение.</p>",
            {
                "left": [
                    {"id": "l1", "text": "Медицентър"},
                    {"id": "l2", "text": "Ортоцентър"},
                    {"id": "l3", "text": "Център на описаната окръжност"},
                ],
                "right": [
                    {"id": "r1", "text": "Пресечна точка на медианите"},
                    {"id": "r2", "text": "Пресечна точка на височините"},
                    {"id": "r3", "text": "Пресечна точка на симетралите"},
                    {"id": "r4", "text": "Пресечна точка на ъглополовящите"},
                ],
                "pairs": {"l1": "r1", "l2": "r2", "l3": "r3"},
            },
            points=3,
            topic="8. Вписани и описани многоъгълници",
        ),
        _q(
            "ordering",
            "<p>Подредете стъпките за решаване на квадратно уравнение по формулата.</p>",
            {
                "items": [
                    {"id": "i1", "text": "Записваме коефициентите $a$, $b$, $c$"},
                    {"id": "i2", "text": "Пресмятаме $D=b^2-4ac$"},
                    {"id": "i3", "text": "Определяме броя на корените според знака на $D$"},
                    {"id": "i4", "text": "Пресмятаме $x_{1,2}=\\frac{-b\\pm\\sqrt D}{2a}$"},
                ],
                "correct_order": ["i1", "i2", "i3", "i4"],
            },
            topic="5. Квадратни уравнения",
        ),
        _q(
            "grouping",
            "<p>Разпределете изразите според това дали са рационални или ирационални числа.</p>",
            {
                "groups": [{"id": "g1", "name": "Рационални"}, {"id": "g2", "name": "Ирационални"}],
                "items": [
                    {"id": "i1", "text": "$\\sqrt{16}$", "group": "g1"},
                    {"id": "i2", "text": "$\\sqrt{3}$", "group": "g2"},
                    {"id": "i3", "text": "$\\frac{7}{3}$", "group": "g1"},
                    {"id": "i4", "text": "$\\sqrt{8}$", "group": "g2"},
                    {"id": "i5", "text": "$-2{,}5$", "group": "g1"},
                    {"id": "i6", "text": "$1+\\sqrt{2}$", "group": "g2"},
                ],
            },
            points=2,
            topic="4. Квадратен корен",
        ),
        _q(
            "dropdown_blank",
            "<p>Изберете правилните думи.</p>",
            {
                "text": "Два вектора са [[1]], ако лежат на една права или на успоредни прави. Сборът на два противоположни вектора е [[2]] вектор.",
                "blanks": {
                    "1": {"options": ["колинеарни", "равни", "противопосочни"], "correct": "колинеарни"},
                    "2": {"options": ["нулевият", "единичният", "противоположният"], "correct": "нулевият"},
                },
            },
            topic="2. Вектори",
        ),
        _q(
            "open",
            "<p>Докажете, че средната отсечка в триъгълник е успоредна на третата страна и е равна на половината от нея. Опишете накратко доказателството.</p>",
            {
                "model_answer": "<p>Използва се подобие на триъгълници (или векторен метод): $\\vec{MN}=\\frac12\\vec{BC}$.</p>",
                "min_words": 30,
            },
            difficulty=3,
            points=3,
            topic="3. Триъгълник и трапец",
        ),
    ]


def history_questions() -> list[dict]:
    return [
        _q(
            "single_choice",
            "<p>Кой е авторът на „История славянобългарска“ (1762 г.)?</p>",
            {
                "options": [
                    {"id": "a", "text": "Софроний Врачански"},
                    {"id": "b", "text": "Паисий Хилендарски"},
                    {"id": "c", "text": "Георги Раковски"},
                    {"id": "d", "text": "Васил Левски"},
                ],
                "correct": "b",
            },
            difficulty=1,
            topic="Тема 1. Българско възраждане (XVIII – XIX в.)",
        ),
        _q(
            "ordering",
            "<p>Подредете събитията в хронологичен ред.</p>",
            {
                "items": [
                    {"id": "i1", "text": "Априлско въстание"},
                    {"id": "i2", "text": "Учредяване на Българската екзархия"},
                    {"id": "i3", "text": "Руско-турска освободителна война"},
                    {"id": "i4", "text": "Съединение на Княжество България и Източна Румелия"},
                ],
                "correct_order": ["i2", "i1", "i3", "i4"],
            },
            points=2,
            topic="Тема 1. Българско възраждане (XVIII – XIX в.)",
        ),
        _q(
            "true_false",
            "<p>Преценете твърденията за Търновската конституция.</p>",
            {
                "statements": [
                    {"id": "s1", "text": "Приета е през 1879 г. от Учредителното събрание.", "answer": True},
                    {"id": "s2", "text": "Установява абсолютна монархия без парламент.", "answer": False},
                    {"id": "s3", "text": "Гарантира основни граждански права и свободи.", "answer": True},
                ]
            },
            points=2,
            topic="Тема 2. България от Освобождението до края на Втората световна война",
        ),
        _q(
            "matching",
            "<p>Свържете личността с нейната дейност.</p>",
            {
                "left": [
                    {"id": "l1", "text": "Васил Левски"},
                    {"id": "l2", "text": "Христо Ботев"},
                    {"id": "l3", "text": "Стефан Стамболов"},
                ],
                "right": [
                    {"id": "r1", "text": "Изгражда Вътрешната революционна организация"},
                    {"id": "r2", "text": "Поет и войвода на чета през 1876 г."},
                    {"id": "r3", "text": "Министър-председател, политика на модернизация"},
                    {"id": "r4", "text": "Пръв български екзарх"},
                ],
                "pairs": {"l1": "r1", "l2": "r2", "l3": "r3"},
            },
            points=3,
            topic="Тема 1. Българско възраждане (XVIII – XIX в.)",
        ),
        _q(
            "multi_choice",
            "<p>Кои от изброените са последици от Берлинския договор (1878 г.)?</p>",
            {
                "options": [
                    {"id": "a", "text": "Създаване на Княжество България"},
                    {"id": "b", "text": "Обявяване на Независимостта на България"},
                    {"id": "c", "text": "Създаване на автономната област Източна Румелия"},
                    {"id": "d", "text": "Македония и Одринско остават в Османската империя"},
                ],
                "correct": ["a", "c", "d"],
            },
            points=2,
            topic="Тема 2. България от Освобождението до края на Втората световна война",
        ),
        _q(
            "fill_blank",
            "<p>Попълнете годините.</p>",
            {
                "text": "Независимостта на България е обявена през [[1]] г., а Съединението е извършено през [[2]] г.",
                "blanks": {"1": {"answers": ["1908"]}, "2": {"answers": ["1885"]}},
            },
            points=2,
            topic="Тема 2. България от Освобождението до края на Втората световна война",
        ),
        _q(
            "grouping",
            "<p>Разпределете понятията според историческия период.</p>",
            {
                "groups": [
                    {"id": "g1", "name": "Възраждане"},
                    {"id": "g2", "name": "България 1944 – 1989 г."},
                ],
                "items": [
                    {"id": "i1", "text": "читалище", "group": "g1"},
                    {"id": "i2", "text": "култ към личността", "group": "g2"},
                    {"id": "i3", "text": "Екзархия", "group": "g1"},
                    {"id": "i4", "text": "Източен блок", "group": "g2"},
                    {"id": "i5", "text": "национална революция", "group": "g1"},
                    {"id": "i6", "text": "пропаганда", "group": "g2"},
                ],
            },
            points=2,
            topic="Тема 3. България след Втората световна война до 1989 г.",
        ),
        _q(
            "find_errors",
            "<p>Открийте и поправете грешките в текста (правописни и фактологични).</p>",
            {
                "text": "Априлското възтание избухва през 1876 г. в Коприфщица. Водач на Ботевата чета е Христо Ботев.",
                "errors": [{"index": 1, "correct": "въстание"}, {"index": 7, "correct": "Копривщица."}],
            },
            difficulty=3,
            points=2,
            topic="Тема 1. Българско възраждане (XVIII – XIX в.)",
        ),
        _q(
            "reading",
            "<p>Прочетете текста и отговорете на въпросите.</p>",
            {
                "passage": "<p>След Втората световна война в България се установява еднопартийно управление. Чрез референдум през 1946 г. монархията е премахната и страната е обявена за народна република. Икономиката е национализирана, а земеделието – колективизирано. Българската държава става част от Източния блок и следва политиката на СССР.</p>",
                "sub_questions": [
                    {
                        "id": "q1",
                        "type": "single_choice",
                        "stem": "<p>През коя година е проведен референдумът за премахване на монархията?</p>",
                        "points": 1,
                        "data": {
                            "options": [
                                {"id": "a", "text": "1944"},
                                {"id": "b", "text": "1946"},
                                {"id": "c", "text": "1948"},
                            ],
                            "correct": "b",
                        },
                    },
                    {
                        "id": "q2",
                        "type": "true_false",
                        "stem": "<p>Преценете твърденията според текста.</p>",
                        "points": 1,
                        "data": {
                            "statements": [
                                {"id": "s1", "text": "Икономиката е национализирана.", "answer": True},
                                {"id": "s2", "text": "България следва политиката на САЩ.", "answer": False},
                            ]
                        },
                    },
                ],
            },
            points=2,
            topic="Тема 3. България след Втората световна война до 1989 г.",
        ),
        _q(
            "open",
            "<p>Обяснете накратко какво означава понятието „национална катастрофа“ и дайте пример от българската история.</p>",
            {
                "model_answer": "<p>Загуба на територии и население след неуспешна война – напр. Междусъюзническата война 1913 г. или Първата световна война.</p>",
                "min_words": 30,
            },
            difficulty=3,
            points=3,
            topic="Тема 2. България от Освобождението до края на Втората световна война",
        ),
    ]


def bel_questions() -> list[dict]:
    return [
        _q(
            "single_choice",
            "<p>Кое от изреченията съдържа лексикална грешка?</p>",
            {
                "options": [
                    {"id": "a", "text": "Той направи добро впечатление на комисията."},
                    {"id": "b", "text": "Тя изигра важна роля в проекта."},
                    {"id": "c", "text": "Взехме решение да отложим срещата."},
                    {"id": "d", "text": "Постигнахме голям напредък."},
                ],
                "correct": "a",
            },
            difficulty=2,
            topic="2. Прилагане на лексикалната норма в речевата практика (езиков практикум)",
        ),
        _q(
            "find_errors",
            "<p>Открийте и поправете грешките в текста.</p>",
            {
                "text": "Уважаеми госпожо Петрова, кандидатствам за позицията защото имам богат опид в сферата.",
                "errors": [
                    {"index": 0, "correct": "Уважаема"},
                    {"index": 5, "correct": "позицията,"},
                    {"index": 9, "correct": "опит"},
                ],
            },
            difficulty=3,
            points=3,
            topic="Мотивационно писмо",
        ),
        _q(
            "dropdown_blank",
            "<p>Изберете подходящия синоним.</p>",
            {
                "text": "Врабчето [[1]] по оградата. След състезанието Борис беше [[2]] от успеха си.",
                "blanks": {
                    "1": {"options": ["подскача", "пълзи", "плува"], "correct": "подскача"},
                    "2": {"options": ["щастлив", "тъжен", "уморен"], "correct": "щастлив"},
                },
            },
            difficulty=1,
            topic="2. Прилагане на лексикалната норма в речевата практика (езиков практикум)",
        ),
        _q(
            "true_false",
            "<p>Преценете твърденията за мотивационното писмо.</p>",
            {
                "statements": [
                    {
                        "id": "s1",
                        "text": "Мотивационното писмо се съобразява с адресата и целта на кандидатстването.",
                        "answer": True,
                    },
                    {
                        "id": "s2",
                        "text": "В мотивационното писмо е уместно използването на жаргон.",
                        "answer": False,
                    },
                    {
                        "id": "s3",
                        "text": "Писмото има установена структура: обръщение, изложение, заключение, подпис.",
                        "answer": True,
                    },
                ]
            },
            points=2,
            topic="Мотивационно писмо",
        ),
        _q(
            "matching",
            "<p>Свържете понятието с определението му.</p>",
            {
                "left": [
                    {"id": "l1", "text": "Стилистична грешка"},
                    {"id": "l2", "text": "Стилистичен ефект"},
                    {"id": "l3", "text": "Библиография"},
                ],
                "right": [
                    {"id": "r1", "text": "Неуместна употреба на езиково средство спрямо сферата на общуване"},
                    {"id": "r2", "text": "Целенасочено отклонение от нормата с въздействаща цел"},
                    {"id": "r3", "text": "Списък на използваните източници, оформен по правила"},
                    {"id": "r4", "text": "Кратко писмено изложение на чужд текст"},
                ],
                "pairs": {"l1": "r1", "l2": "r2", "l3": "r3"},
            },
            points=3,
            topic="3. Анализ и редактиране на стилистични грешки (езиков практикум)",
        ),
        _q(
            "ordering",
            "<p>Подредете частите на мотивационното писмо в правилната последователност.</p>",
            {
                "items": [
                    {"id": "i1", "text": "Обръщение към адресата"},
                    {"id": "i2", "text": "Представяне на кандидата и целта на писмото"},
                    {"id": "i3", "text": "Аргументи: опит, умения, мотивация"},
                    {"id": "i4", "text": "Заключение и готовност за контакт"},
                    {"id": "i5", "text": "Поздрав и подпис"},
                ],
                "correct_order": ["i1", "i2", "i3", "i4", "i5"],
            },
            points=2,
            topic="Мотивационно писмо",
        ),
        _q(
            "grouping",
            "<p>Разпределете изразите според регистъра им.</p>",
            {
                "groups": [
                    {"id": "g1", "name": "Официално-делови стил"},
                    {"id": "g2", "name": "Разговорен стил"},
                ],
                "items": [
                    {"id": "i1", "text": "Уведомяваме Ви, че…", "group": "g1"},
                    {"id": "i2", "text": "Абе, виж сега…", "group": "g2"},
                    {"id": "i3", "text": "Моля да бъда назначен на длъжност…", "group": "g1"},
                    {"id": "i4", "text": "Яко стана!", "group": "g2"},
                    {"id": "i5", "text": "С уважение,", "group": "g1"},
                    {"id": "i6", "text": "Айде чао.", "group": "g2"},
                ],
            },
            points=2,
            topic="1. Речевото поведение в комуникативната практика",
        ),
        _q(
            "reading",
            "<p>Прочетете откъса от мотивационно писмо и отговорете на въпросите.</p>",
            {
                "passage": "<p>Уважаема г-жо Директор,<br>Кандидатствам за стажантска позиция в библиотеката на училището. Интересът ми към книгите датира от детството ми, а през последните две години участвах в организирането на литературни четения. Вярвам, че умението ми да работя в екип и познанията ми за библиографското описание ще бъдат полезни за екипа Ви.</p>",
                "sub_questions": [
                    {
                        "id": "q1",
                        "type": "single_choice",
                        "stem": "<p>Каква е целта на текста?</p>",
                        "points": 1,
                        "data": {
                            "options": [
                                {"id": "a", "text": "Да представи кандидата и мотивите му"},
                                {"id": "b", "text": "Да опише историята на библиотеката"},
                                {"id": "c", "text": "Да отправи оплакване"},
                            ],
                            "correct": "a",
                        },
                    },
                    {
                        "id": "q2",
                        "type": "fill_blank",
                        "stem": "<p>За каква позиция кандидатства авторът?</p>",
                        "points": 1,
                        "data": {"text": "За [[1]] позиция.", "blanks": {"1": {"answers": ["стажантска"]}}},
                    },
                    {
                        "id": "q3",
                        "type": "open",
                        "stem": "<p>Кой аргумент на кандидата е най-убедителен и защо?</p>",
                        "points": 2,
                        "data": {"model_answer": "<p>Свободен отговор с аргументация.</p>"},
                    },
                ],
            },
            points=4,
            difficulty=2,
            topic="Мотивационно писмо",
        ),
        _q(
            "open",
            "<p>Напишете кратко мотивационно писмо (до 150 думи) за участие в ученическа конференция. Спазвайте структурата и книжовните норми.</p>",
            {
                "model_answer": "<p>Критерии: структура, уместност, книжовни норми, аргументация.</p>",
                "min_words": 80,
            },
            difficulty=3,
            points=6,
            topic="Мотивационно писмо",
        ),
        _q(
            "file_upload",
            "<p>Качете снимка/файл с ръкописно оформена библиография на три източника по избрана от вас тема.</p>",
            {
                "instructions": "<p>Допустими формати: PDF, JPG, PNG.</p>",
                "allowed_ext": ["pdf", "jpg", "jpeg", "png"],
                "max_mb": 10,
            },
            points=3,
            topic="Библиография",
        ),
    ]


def _make_test(
    db: Session, owner: User, cur: Curriculum, title: str, description: str, questions: list[dict]
) -> Test:
    test = Test(
        owner_id=owner.id,
        title=title,
        description=description,
        subject=cur.subject,
        grade_label=cur.grade_label,
        curriculum_id=cur.id,
        sections=[
            {
                "key": "s1",
                "title": "Задачи",
                "type": "",
                "count": len(questions),
                "difficulty": 2,
                "topics": [],
                "points": 1,
                "source": "manual",
                "instructions": "",
            }
        ],
        settings={},
        status="ready",
    )
    db.add(test)
    db.flush()
    for i, q in enumerate(questions):
        db.add(
            Question(
                owner_id=owner.id,
                test_id=test.id,
                section_key="s1",
                position=i,
                type=q["type"],
                stem=q["stem"],
                data=q["data"],
                difficulty=q["difficulty"],
                points=q["points"],
                curriculum_id=cur.id,
                topic=q["topic"],
                source="manual",
            )
        )
        # копие и в банката на учителя
        db.add(
            Question(
                owner_id=owner.id,
                test_id=None,
                position=i,
                type=q["type"],
                stem=q["stem"],
                data=q["data"],
                difficulty=q["difficulty"],
                points=q["points"],
                curriculum_id=cur.id,
                topic=q["topic"],
                source="manual",
            )
        )
    db.flush()
    return test


def seed(db: Session) -> bool:
    """Зарежда демо данните, ако базата е празна. Връща True ако е заредено."""
    load_curricula_from_disk(db)
    if db.scalar(select(User.id).limit(1)):
        return False

    teachers: dict[str, User] = {}
    for username, name, subject, color in TEACHERS:
        u = User(username=username, full_name=name, role="teacher", subject=subject, avatar_color=color)
        db.add(u)
        teachers[subject] = u
    students: dict[str, list[User]] = {}
    ci = 0
    for grade, names in STUDENTS.items():
        students[grade] = []
        for name in names:
            u = User(
                username=_username(name),
                full_name=name,
                role="student",
                grade_label=grade,
                avatar_color=COLORS[ci % len(COLORS)],
            )
            ci += 1
            db.add(u)
            students[grade].append(u)
    db.flush()

    curs = {c.code: c for c in db.scalars(select(Curriculum)).all()}
    plan = [
        (
            "Математика",
            "math-8",
            "8б",
            "8б – Математика",
            "Квадратни уравнения и корени – входно ниво",
            math_questions(),
        ),
        (
            "История и цивилизации",
            "history-7",
            "7а",
            "7а – История и цивилизации",
            "Възраждане и нова българска държава",
            history_questions(),
        ),
        (
            "Български език и литература",
            "bel-12",
            "12в",
            "12в – Български език",
            "Лексикална норма и мотивационно писмо",
            bel_questions(),
        ),
    ]
    now = utcnow()
    for subject, code, grade, class_name, test_title, questions in plan:
        teacher = teachers[subject]
        cur = curs[code]
        room = Classroom(name=class_name, teacher_id=teacher.id, subject=subject, curriculum_id=cur.id)
        db.add(room)
        db.flush()
        for s in students[grade]:
            db.add(ClassroomStudent(classroom_id=room.id, student_id=s.id))
        test = _make_test(
            db,
            teacher,
            cur,
            test_title,
            f"Примерен тест по {subject.lower()} с различни типове задачи.",
            questions,
        )
        a = Assignment(
            test_id=test.id,
            teacher_id=teacher.id,
            title=test.title,
            mode="practice",
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(days=14),
            time_limit_min=None,
            attempts_allowed=2,
            shuffle_questions=False,
            shuffle_options=True,
            show_results="immediately",
        )
        db.add(a)
        db.flush()
        db.add(AssignmentClassroom(assignment_id=a.id, classroom_id=room.id))
        exam = Assignment(
            test_id=test.id,
            teacher_id=teacher.id,
            title=f"Контролна работа: {test.title}",
            mode="exam",
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(days=7),
            time_limit_min=40,
            attempts_allowed=1,
            shuffle_questions=True,
            shuffle_options=True,
            show_results="after_end",
            max_warnings=3,
        )
        db.add(exam)
        db.flush()
        db.add(AssignmentClassroom(assignment_id=exam.id, classroom_id=room.id))
    db.flush()
    return True
