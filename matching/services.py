import secrets

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError


CAREER_ROLE_SKILLS = (
    {
        "title": "Backend Developer",
        "description": "Builds application logic, APIs, and server-side systems.",
        "skills": {"python", "django", "java", "sql", "api"},
    },
    {
        "title": "Frontend Developer",
        "description": "Builds the interactive parts of websites and web apps.",
        "skills": {"javascript", "react", "html", "css", "ui"},
    },
    {
        "title": "Software Developer",
        "description": "Designs and develops software across different platforms.",
        "skills": {"python", "java", "c", "c++", "javascript"},
    },
    {
        "title": "Data Analyst",
        "description": "Uses data and queries to help answer business questions.",
        "skills": {"python", "sql", "excel", "data analysis", "statistics"},
    },
    {
        "title": "QA Automation Engineer",
        "description": "Tests software and automates checks for quality.",
        "skills": {"python", "java", "testing", "selenium"},
    },
    {
        "title": "Cloud Engineer",
        "description": "Helps build and operate services on cloud platforms.",
        "skills": {"cloud computing", "aws", "azure", "linux", "docker"},
    },
    {
        "title": "UI/UX Designer",
        "description": "Designs user-friendly digital products and interfaces.",
        "skills": {"design", "figma", "ui", "ux", "user research"},
    },
    {
        "title": "Cybersecurity Analyst",
        "description": "Helps protect systems, networks, and information.",
        "skills": {"cybersecurity", "security", "networking", "linux"},
    },
)


def validate_student_login_username(roll_number, exclude_user_id=None):
    user_model = get_user_model()
    username_field = user_model.USERNAME_FIELD
    users = user_model._default_manager.filter(
        **{f"{username_field}__iexact": roll_number}
    )
    if exclude_user_id is not None:
        users = users.exclude(pk=exclude_user_id)
    if users.exists():
        raise ValidationError(
            "This roll number is already used by another login account.",
            code="duplicate_login_username",
        )


def create_student_login(student):
    if student.user_id:
        return None

    validate_student_login_username(student.roll_number)
    user_model = get_user_model()
    username_field = user_model.USERNAME_FIELD
    user = user_model(**{username_field: student.roll_number})
    if hasattr(user, "email"):
        user.email = student.email

    password = f"{secrets.randbelow(1_000_000):06d}"
    user.set_password(password)
    user.save()

    student.user = user
    student.login_code = password
    student.save(update_fields=["user", "login_code"])
    return password


def reset_student_login_code(student):
    if student.user_id is None:
        return create_student_login(student)

    password = f"{secrets.randbelow(1_000_000):06d}"
    student.user.set_password(password)
    student.user.save(update_fields=["password"])
    student.login_code = password
    student.save(update_fields=["login_code"])
    return password


def sync_student_login_username(student):
    if not student.user_id:
        return

    user = student.user
    username_field = user.USERNAME_FIELD
    current_username = getattr(user, username_field)
    if current_username.casefold() == student.roll_number.casefold():
        return

    validate_student_login_username(
        student.roll_number,
        exclude_user_id=user.pk,
    )
    setattr(user, username_field, student.roll_number)
    user.save(update_fields=[username_field])


def recommend_career_roles(skills, limit=3):
    normalized_skills = {skill.strip().casefold() for skill in skills if skill.strip()}
    recommendations = []
    for role in CAREER_ROLE_SKILLS:
        matched_skills = sorted(normalized_skills.intersection(role["skills"]))
        if matched_skills:
            recommendations.append(
                {
                    "title": role["title"],
                    "description": role["description"],
                    "matched_skills": matched_skills,
                }
            )

    recommendations.sort(key=lambda role: (-len(role["matched_skills"]), role["title"]))
    return recommendations[:limit]


def calculate_match(student1, student2):
    teach1 = set(student1.teach_skills)
    learn1 = set(student1.learn_skills)
    teach2 = set(student2.teach_skills)
    learn2 = set(student2.learn_skills)

    first_match = teach1.intersection(learn2)
    second_match = teach2.intersection(learn1)
    total_possible = len(learn1) + len(learn2)
    percentage = (
        (len(first_match) + len(second_match)) / total_possible * 100
        if total_possible
        else 0
    )

    return first_match, second_match, percentage
