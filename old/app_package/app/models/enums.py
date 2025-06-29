"""
列挙型定義
"""
from enum import Enum

class ResidenceType(Enum):
    """住居タイプ"""
    RENTAL = '賃貸'
    OWNED_WITH_LOAN = '持家（ローンあり）'
    OWNED_WITHOUT_LOAN = '持家（ローンなし）'

class KindergartenType(Enum):
    """幼稚園タイプ"""
    NONE = '未就園'
    PUBLIC = '公立幼稚園'
    PRIVATE = '私立幼稚園'

class ElementaryType(Enum):
    """小学校タイプ"""
    PUBLIC = '公立小学校'
    PRIVATE = '私立小学校'

class JuniorType(Enum):
    """中学校タイプ"""
    PUBLIC = '公立中学校'
    PRIVATE = '私立中学校'

class HighType(Enum):
    """高校タイプ"""
    PUBLIC = '公立高校'
    PRIVATE = '私立高校'

class CollegeType(Enum):
    """大学タイプ"""
    NONE = '進学しない'
    NATIONAL = '国公立大学'
    PRIVATE_LIBERAL = '私立文系'
    PRIVATE_SCIENCE = '私立理系'
    JUNIOR_COLLEGE = '短期大学'
    VOCATIONAL = '専門学校'

class EventCategory(Enum):
    """イベントカテゴリ"""
    MARRIAGE = '結婚'
    BIRTH = '出産'
    CAR = '車'
    MOVING = '引越'
    CARE = '介護'
    FUNERAL = '葬儀'
    TRAVEL = '旅行'
    OTHER = 'その他'

class RepaymentMethod(Enum):
    """返済方法"""
    EQUAL_PAYMENT = '元利均等'
    EQUAL_PRINCIPAL = '元金均等' 