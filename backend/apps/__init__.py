from .users.apps import UsersConfig
from .courses.apps import CoursesConfig
from .videos.apps import VideosConfig
from .assignments.apps import AssignmentsConfig
from .exams.apps import ExamsConfig
from .classes.apps import ClassesConfig
from .analytics.apps import AnalyticsConfig

__all__ = [
    'UsersConfig',
    'CoursesConfig',
    'VideosConfig',
    'AssignmentsConfig',
    'ExamsConfig',
    'ClassesConfig',
    'AnalyticsConfig'
]
