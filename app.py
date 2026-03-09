from flask import Flask, jsonify, request, render_template, send_file
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2._page import PageObject
from PyPDF2.generic import NameObject, BooleanObject
from datetime import datetime, date
from copy import deepcopy
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, inspect, text
import os

# ...
app = Flask(__name__)


# --- Config DB (Postgres en Railway vía DATABASE_URL) ---
db_url = os.environ.get("DATABASE_URL")

# Railway suele entregar postgres://; lo adaptamos a SQLAlchemy con psycopg3
if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url or "sqlite:///arabia_tkd.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

with app.app_context():
    try:
        db.create_all()

        with db.engine.begin() as conn:
            inspector = inspect(conn)
            if 'students' in inspector.get_table_names():
                student_columns = {col['name'] for col in inspector.get_columns('students')}
                student_column_defs = {
                    'notes': 'TEXT',
                    'status': "TEXT DEFAULT 'activo'",
                    'tutor_type': "TEXT DEFAULT 'padre'",
                    'father_birthdate': 'DATE',
                    'mother_birthdate': 'DATE',
                }
                for column_name, column_def in student_column_defs.items():
                    if column_name not in student_columns:
                        conn.execute(text(f"ALTER TABLE students ADD COLUMN {column_name} {column_def}"))
    except Exception:
        # Si falla (por ejemplo en SQLite viejo), se ignora y se asume que la tabla se recreará en limpio.
        pass

    # Asegurar columnas nuevas en fee_payments (migración liviana, idempotente)
    try:
        with db.engine.begin() as conn:
            inspector = inspect(conn)
            if 'fee_payments' in inspector.get_table_names():
                payment_columns = {col['name'] for col in inspector.get_columns('fee_payments')}
                payment_column_defs = {
                    'method': "TEXT DEFAULT 'cash'",
                    'reference': 'TEXT',
                    'notes': 'TEXT',
                }
                for column_name, column_def in payment_column_defs.items():
                    if column_name not in payment_columns:
                        conn.execute(text(f"ALTER TABLE fee_payments ADD COLUMN {column_name} {column_def}"))
    except Exception:
        pass

class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    last_name = db.Column(db.String(120))
    first_name = db.Column(db.String(120))
    dni = db.Column(db.String(20))
    gender = db.Column(db.String(20))
    birthdate = db.Column(db.Date)
    blood = db.Column(db.String(10))
    nationality = db.Column(db.String(80))
    province = db.Column(db.String(80))
    country = db.Column(db.String(80))
    city = db.Column(db.String(80))
    address = db.Column(db.String(200))
    zip = db.Column(db.String(20))
    school = db.Column(db.String(120))
    belt = db.Column(db.String(40))
    father_name = db.Column(db.String(200))
    mother_name = db.Column(db.String(200))
    father_birthdate = db.Column(db.Date)
    mother_birthdate = db.Column(db.Date)
    father_phone = db.Column(db.String(40))
    mother_phone = db.Column(db.String(40))
    parent_email = db.Column(db.String(120))
    notes = db.Column(db.Text)
    status = db.Column(db.String(10), default='activo')
    tutor_type = db.Column(db.String(20), default='padre')  # 'padre' | 'madre'


class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD
    time = db.Column(db.String(8))  # HH:MM
    title = db.Column(db.String(200))
    type = db.Column(db.String(20), nullable=False, default="general")  # 'general' | 'exam'
    level = db.Column(db.String(80))
    place = db.Column(db.String(160))
    notes = db.Column(db.Text)


class ExamInscription(db.Model):
    __tablename__ = "exam_inscriptions"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)


class FeePayment(db.Model):
    __tablename__ = "fee_payments"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    payment_date = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    method = db.Column(db.String(20), default='cash')  # 'cash' | 'transfer'
    reference = db.Column(db.String(120))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FeeConfig(db.Model):
    __tablename__ = "fee_config"

    id = db.Column(db.Integer, primary_key=True)
    monthly_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    due_day = db.Column(db.Integer, nullable=False, default=10)
    proration_mode = db.Column(db.String(20), nullable=False, default='days')  # 'days' | 'percent'
    proration_percent_default = db.Column(db.Numeric(5, 2), nullable=False, default=100)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StudentFeeSettings(db.Model):
    __tablename__ = "student_fee_settings"

    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), primary_key=True)
    discount_type = db.Column(db.String(20))  # 'percent' | 'amount'
    discount_value = db.Column(db.Numeric(10, 2), nullable=False, default=0)


class FeeCharge(db.Model):
    __tablename__ = "fee_charges"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    period = db.Column(db.String(7), nullable=False)  # YYYY-MM
    due_date = db.Column(db.Date, nullable=False)
    base_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    proration_mode = db.Column(db.String(20), nullable=False, default='percent')  # 'days' | 'percent'
    proration_percent = db.Column(db.Numeric(5, 2), nullable=False, default=100)
    proration_start_date = db.Column(db.Date)
    final_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'period', name='uq_fee_charges_student_period'),
    )


class FeeAllocation(db.Model):
    __tablename__ = "fee_allocations"

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("fee_payments.id"), nullable=False)
    charge_id = db.Column(db.Integer, db.ForeignKey("fee_charges.id"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@app.route('/')
def index():
    return render_template('index.html')


# --- Students CRUD ---
@app.route('/api/students', methods=['GET', 'POST'])
def api_students():
    if request.method == 'GET':
        # Asegurar que la columna tutor_type exista en entornos como Railway (Postgres).
        # Si ya existe o la BD no soporta IF NOT EXISTS, se ignora cualquier error.
        try:
            with db.engine.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE IF EXISTS students "
                    "ADD COLUMN IF NOT EXISTS tutor_type TEXT DEFAULT 'padre'"
                ))
                conn.commit()
        except Exception:
            pass

        students_q = Student.query.order_by(
            (Student.last_name.is_(None)).asc(),
            Student.last_name.asc(),
            Student.first_name.asc(),
        ).all()
        result = []
        for s in students_q:
            result.append({
                'id': s.id,
                'full_name': s.full_name,
                'last_name': s.last_name,
                'first_name': s.first_name,
                'dni': s.dni,
                'gender': s.gender,
                'birthdate': s.birthdate.isoformat() if s.birthdate else None,
                'blood': s.blood,
                'nationality': s.nationality,
                'province': s.province,
                'country': s.country,
                'city': s.city,
                'address': s.address,
                'zip': s.zip,
                'school': s.school,
                'belt': s.belt,
                'father_name': s.father_name,
                'mother_name': s.mother_name,
                'father_birthdate': s.father_birthdate.isoformat() if s.father_birthdate else None,
                'mother_birthdate': s.mother_birthdate.isoformat() if s.mother_birthdate else None,
                'father_phone': s.father_phone,
                'mother_phone': s.mother_phone,
                'parent_email': s.parent_email,
                'notes': s.notes,
                'status': s.status,
                'tutor_type': s.tutor_type,
            })
        return jsonify(result)

    data = request.json or {}
    birthdate_val = data.get('birthdate')
    birthdate_parsed = None
    if birthdate_val:
        try:
            birthdate_parsed = datetime.strptime(birthdate_val, '%Y-%m-%d').date()
        except ValueError:
            birthdate_parsed = None

    father_birthdate_val = data.get('father_birthdate')
    father_birthdate_parsed = None
    if father_birthdate_val:
        try:
            father_birthdate_parsed = datetime.strptime(father_birthdate_val, '%Y-%m-%d').date()
        except ValueError:
            father_birthdate_parsed = None

    mother_birthdate_val = data.get('mother_birthdate')
    mother_birthdate_parsed = None
    if mother_birthdate_val:
        try:
            mother_birthdate_parsed = datetime.strptime(mother_birthdate_val, '%Y-%m-%d').date()
        except ValueError:
            mother_birthdate_parsed = None

    student = Student(
        full_name=data.get('full_name', ''),
        last_name=data.get('last_name'),
        first_name=data.get('first_name'),
        dni=data.get('dni'),
        gender=data.get('gender'),
        birthdate=birthdate_parsed,
        blood=data.get('blood'),
        nationality=data.get('nationality'),
        province=data.get('province'),
        country=data.get('country'),
        city=data.get('city'),
        address=data.get('address'),
        zip=data.get('zip'),
        school=data.get('school'),
        belt=data.get('belt'),
        father_name=data.get('father_name'),
        mother_name=data.get('mother_name'),
        father_birthdate=father_birthdate_parsed,
        mother_birthdate=mother_birthdate_parsed,
        father_phone=data.get('father_phone'),
        mother_phone=data.get('mother_phone'),
        parent_email=data.get('parent_email'),
        notes=data.get('notes'),
        status=data.get('status', 'activo'),
        tutor_type=data.get('tutor_type', 'padre'),
    )
    db.session.add(student)
    db.session.commit()

    return jsonify({'id': student.id, 'full_name': student.full_name}), 201


@app.route('/api/students/<int:student_id>', methods=['GET', 'PUT', 'DELETE'])
def api_student_detail(student_id: int):
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'error': 'Alumno no encontrado'}), 404

    if request.method == 'GET':
        return jsonify({
            'id': student.id,
            'full_name': student.full_name,
            'last_name': student.last_name,
            'first_name': student.first_name,
            'dni': student.dni,
            'gender': student.gender,
            'birthdate': student.birthdate.isoformat() if student.birthdate else None,
            'blood': student.blood,
            'nationality': student.nationality,
            'province': student.province,
            'country': student.country,
            'city': student.city,
            'address': student.address,
            'zip': student.zip,
            'school': student.school,
            'belt': student.belt,
            'father_name': student.father_name,
            'mother_name': student.mother_name,
            'father_birthdate': student.father_birthdate.isoformat() if student.father_birthdate else None,
            'mother_birthdate': student.mother_birthdate.isoformat() if student.mother_birthdate else None,
            'father_phone': student.father_phone,
            'mother_phone': student.mother_phone,
            'parent_email': student.parent_email,
            'notes': student.notes,
            'status': student.status,
            'tutor_type': student.tutor_type,
        })

    if request.method == 'PUT':
        data = request.json or {}
        for field in [
            'full_name', 'last_name', 'first_name', 'dni', 'gender', 'blood',
            'nationality', 'province', 'country', 'city', 'address', 'zip',
            'school', 'belt', 'father_name', 'mother_name', 'father_phone',
            'mother_phone', 'parent_email', 'notes', 'status', 'tutor_type',
        ]:
            if field in data:
                setattr(student, field, data[field])

        if 'birthdate' in data:
            try:
                student.birthdate = datetime.strptime(data['birthdate'], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                student.birthdate = None

        if 'father_birthdate' in data:
            try:
                student.father_birthdate = datetime.strptime(data['father_birthdate'], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                student.father_birthdate = None

        if 'mother_birthdate' in data:
            try:
                student.mother_birthdate = datetime.strptime(data['mother_birthdate'], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                student.mother_birthdate = None

        db.session.commit()
        return jsonify({'status': 'ok'})

    if request.method == 'DELETE':
        # Borramos primero todas las cuotas asociadas a este alumno
        try:
            _ensure_fees_tables()
        except Exception:
            pass

        try:
            FeeAllocation.query.filter(
                FeeAllocation.payment_id.in_(
                    db.session.query(FeePayment.id).filter_by(student_id=student.id)
                )
            ).delete(synchronize_session=False)
            FeePayment.query.filter_by(student_id=student.id).delete()
            FeeCharge.query.filter_by(student_id=student.id).delete()
            StudentFeeSettings.query.filter_by(student_id=student.id).delete()
        except Exception:
            # Si las tablas no existen aún o hay algún problema, seguimos con el borrado del alumno.
            db.session.rollback()

        # Luego borramos el alumno en sí
        db.session.delete(student)
        db.session.commit()

        return '', 204


# --- Calendar & Exams ---
@app.route('/api/events', methods=['GET', 'POST'])
def api_events():
    if request.method == 'GET':
        events = Event.query.all()
        result = []
        for e in events:
            result.append({
                'id': e.id,
                'date': e.date,
                'time': e.time,
                'title': e.title,
                'type': e.type,
                'level': e.level,
                'place': e.place,
                'notes': e.notes,
            })
        return jsonify(result)

    data = request.json or {}
    event = Event(
        date=data.get('date'),
        time=data.get('time'),
        title=data.get('title'),
        type=data.get('type') or 'general',
        level=data.get('level'),
        place=data.get('place'),
        notes=data.get('notes'),
    )
    db.session.add(event)
    db.session.commit()
    return jsonify({'id': event.id}), 201


@app.route('/api/events/<int:event_id>', methods=['GET', 'DELETE'])
def api_event_detail(event_id: int):
    event = Event.query.get(event_id)
    if not event:
        return jsonify({'error': 'Evento no encontrado'}), 404

    if request.method == 'GET':
        return jsonify({
            'id': event.id,
            'date': event.date,
            'time': event.time,
            'title': event.title,
            'type': event.type,
            'level': event.level,
            'place': event.place,
            'notes': event.notes,
        })

    # DELETE
    # Borrar primero todas las inscripciones vinculadas a este evento (examen)
    ExamInscription.query.filter_by(event_id=event.id).delete()

    # Luego borrar el evento en sí
    db.session.delete(event)
    db.session.commit()
    return '', 204


@app.route('/api/exams/<int:event_id>/students', methods=['GET', 'PUT'])
def api_exam_students(event_id: int):
    """Gestiona la lista de alumnos inscriptos a un examen.

    GET: devuelve la lista de alumnos inscriptos (mismo formato básico que /api/students, pero filtrado).
    PUT: reemplaza la lista de inscriptos con los IDs enviados en JSON: { "student_ids": [1,2,3] }.
    """

    event = Event.query.get(event_id)
    if not event or event.type != 'exam':
        return jsonify({'error': 'Examen no encontrado'}), 404

    if request.method == 'GET':
        inscriptions = ExamInscription.query.filter_by(event_id=event_id).all()
        student_ids = [ins.student_id for ins in inscriptions]

        if not student_ids:
            return jsonify([])

        students = Student.query.filter(Student.id.in_(student_ids)).all()
        result = []
        for s in students:
            result.append({
                'id': s.id,
                'full_name': s.full_name,
                'last_name': s.last_name,
                'first_name': s.first_name,
                'belt': s.belt,
            })
        return jsonify(result)

    # PUT
    data = request.json or {}
    ids = data.get('student_ids') or []

    # Normalizar a enteros, ignorando valores no válidos
    normalized_ids = []
    for raw_id in ids:
        try:
            normalized_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    # Borrar inscripciones anteriores de ese examen
    ExamInscription.query.filter_by(event_id=event_id).delete()

    # Insertar nuevas
    for sid in normalized_ids:
        db.session.add(ExamInscription(event_id=event_id, student_id=sid))

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'No se pudieron guardar las inscripciones'}), 400

    return jsonify({'event_id': event_id, 'student_ids': normalized_ids})


# --- Fees ---

def _ensure_fees_tables():
    try:
        db.create_all()
    except Exception:
        pass


def _get_fee_config():
    _ensure_fees_tables()
    cfg = FeeConfig.query.order_by(FeeConfig.id.asc()).first()
    if not cfg:
        cfg = FeeConfig(monthly_amount=0, due_day=10, proration_mode='days', proration_percent_default=100)
        db.session.add(cfg)
        db.session.commit()
    return cfg


def _get_student_fee_settings(student_id: int):
    _ensure_fees_tables()
    settings = StudentFeeSettings.query.filter_by(student_id=student_id).first()
    if not settings:
        settings = StudentFeeSettings(student_id=student_id, discount_type=None, discount_value=0)
        db.session.add(settings)
        db.session.commit()
    return settings


def _parse_period(period_raw: str):
    value = (period_raw or '').strip()
    if len(value) != 7 or value[4] != '-':
        return None
    y = value[:4]
    m = value[5:]
    try:
        year = int(y)
        month = int(m)
    except Exception:
        return None
    if month < 1 or month > 12:
        return None
    return {'year': year, 'month': month, 'period': f'{year:04d}-{month:02d}'}


def _parse_iso_date(date_raw):
    value = (date_raw or '').strip() if isinstance(date_raw, str) else date_raw
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), '%Y-%m-%d').date()
    except Exception:
        return None


def _list_periods_from_range(start_raw, end_raw):
    start_date = _parse_iso_date(start_raw)
    end_date = _parse_iso_date(end_raw)
    if not start_date or not end_date:
        return []
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    periods = []
    year = start_date.year
    month = start_date.month
    while (year < end_date.year) or (year == end_date.year and month <= end_date.month):
        periods.append({'year': year, 'month': month, 'period': f'{year:04d}-{month:02d}'})
        month += 1
        if month > 12:
            month = 1
            year += 1
    return periods


def _create_fee_charge(student_id: int, cfg: FeeConfig, settings: StudentFeeSettings, period_info, body):
    existing = FeeCharge.query.filter_by(student_id=student_id, period=period_info['period']).first()
    base_amount = float(cfg.monthly_amount or 0)
    if base_amount <= 0:
        return False
    discount_amount = _compute_discount_amount(base_amount, settings)

    proration_mode = body.get('proration_mode')
    start_date_raw = body.get('start_date')
    proration_percent_raw = body.get('proration_percent')
    proration = _compute_proration_percent(cfg, period_info, proration_mode, start_date_raw, proration_percent_raw)

    net = base_amount - discount_amount
    if net < 0:
        net = 0
    final_amount = round(net * (float(proration['percent']) / 100.0), 2)

    year = period_info['year']
    month = period_info['month']
    due_day = int(cfg.due_day or 10)
    dim = _days_in_month(year, month)
    if due_day > dim:
        due_day = dim
    due_date = date(year, month, due_day)

    if existing:
        has_allocations = FeeAllocation.query.filter_by(charge_id=existing.id).count() > 0
        existing_final_amount = float(existing.final_amount or 0)
        if has_allocations or existing_final_amount > 0:
            return False

        existing.due_date = due_date
        existing.base_amount = round(base_amount, 2)
        existing.discount_amount = round(discount_amount, 2)
        existing.proration_mode = proration['mode']
        existing.proration_percent = proration['percent']
        existing.proration_start_date = proration['start_date']
        existing.final_amount = final_amount
        return True

    charge = FeeCharge(
        student_id=student_id,
        period=period_info['period'],
        due_date=due_date,
        base_amount=round(base_amount, 2),
        discount_amount=round(discount_amount, 2),
        proration_mode=proration['mode'],
        proration_percent=proration['percent'],
        proration_start_date=proration['start_date'],
        final_amount=final_amount,
    )
    db.session.add(charge)
    return True


def _days_in_month(year: int, month: int):
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return (next_month - date(year, month, 1)).days


def _compute_discount_amount(base_amount: float, settings: StudentFeeSettings):
    dtype = (settings.discount_type or '').strip().lower()
    try:
        dval = float(settings.discount_value or 0)
    except Exception:
        dval = 0
    if dval < 0:
        dval = 0
    if dtype == 'percent':
        discount = base_amount * (dval / 100.0)
    elif dtype == 'amount':
        discount = dval
    else:
        discount = 0
    if discount > base_amount:
        discount = base_amount
    return round(discount, 2)


def _compute_proration_percent(cfg: FeeConfig, period_info, proration_mode: str, start_date_raw: str, proration_percent_raw):
    mode = (proration_mode or cfg.proration_mode or 'days').strip().lower()
    if mode not in ('days', 'percent'):
        mode = 'days'

    if mode == 'percent':
        if proration_percent_raw is None or proration_percent_raw == '':
            try:
                pct = float(cfg.proration_percent_default or 100)
            except Exception:
                pct = 100
        else:
            try:
                pct = float(proration_percent_raw)
            except Exception:
                pct = 100
        if pct < 0:
            pct = 0
        if pct > 100:
            pct = 100
        return {'mode': 'percent', 'percent': round(pct, 2), 'start_date': None}

    start_date = None
    if start_date_raw:
        try:
            start_date = datetime.strptime(start_date_raw, '%Y-%m-%d').date()
        except Exception:
            start_date = None
    if not start_date:
        try:
            pct = float(cfg.proration_percent_default or 100)
        except Exception:
            pct = 100
        if pct < 0:
            pct = 0
        if pct > 100:
            pct = 100
        return {'mode': 'days', 'percent': round(pct, 2), 'start_date': None}

    year = period_info['year']
    month = period_info['month']
    dim = _days_in_month(year, month)
    if start_date.year != year or start_date.month != month:
        pct = 100
    else:
        remaining = dim - start_date.day + 1
        if remaining < 0:
            remaining = 0
        pct = (remaining / dim) * 100.0
    if pct < 0:
        pct = 0
    if pct > 100:
        pct = 100
    return {'mode': 'days', 'percent': round(pct, 2), 'start_date': start_date}


def _get_charge_allocated_amounts(charge_ids):
    if not charge_ids:
        return {}
    allocations = FeeAllocation.query.filter(FeeAllocation.charge_id.in_(charge_ids)).all()
    out = {}
    for a in allocations:
        out[a.charge_id] = out.get(a.charge_id, 0.0) + float(a.amount)
    return out


def _serialize_student_fees(student_id: int):
    _ensure_fees_tables()
    cfg = _get_fee_config()
    settings = _get_student_fee_settings(student_id)

    charges = FeeCharge.query.filter_by(student_id=student_id).order_by(FeeCharge.period.desc()).all()
    charge_ids = [c.id for c in charges]
    allocated_map = _get_charge_allocated_amounts(charge_ids)
    today = date.today()

    charges_out = []
    overdue_total = 0.0
    for c in charges:
        paid = allocated_map.get(c.id, 0.0)
        total = float(c.final_amount or 0)
        balance = round(total - paid, 2)
        if balance < 0:
            balance = 0.0

        if balance == 0 and total > 0:
            status = 'paid'
        elif paid > 0:
            status = 'partial'
        else:
            status = 'pending'

        is_overdue = (c.due_date is not None) and (today > c.due_date) and (status != 'paid')
        if is_overdue:
            overdue_total += balance

        charges_out.append({
            'id': c.id,
            'period': c.period,
            'due_date': c.due_date.isoformat() if c.due_date else None,
            'base_amount': float(c.base_amount or 0),
            'discount_amount': float(c.discount_amount or 0),
            'proration_mode': c.proration_mode,
            'proration_percent': float(c.proration_percent or 0),
            'proration_start_date': c.proration_start_date.isoformat() if c.proration_start_date else None,
            'final_amount': total,
            'paid_amount': round(paid, 2),
            'balance': balance,
            'status': status,
            'overdue': is_overdue,
        })

    payments = FeePayment.query.filter_by(student_id=student_id).order_by(FeePayment.payment_date.desc(), FeePayment.id.desc()).all()
    payment_ids = [p.id for p in payments]
    allocations = []
    if payment_ids:
        allocations = FeeAllocation.query.filter(FeeAllocation.payment_id.in_(payment_ids)).all()
    alloc_by_payment = {}
    for a in allocations:
        alloc_by_payment.setdefault(a.payment_id, []).append({
            'id': a.id,
            'charge_id': a.charge_id,
            'amount': float(a.amount),
        })

    payments_out = []
    for p in payments:
        payments_out.append({
            'id': p.id,
            'payment_date': p.payment_date,
            'amount': float(p.amount),
            'method': getattr(p, 'method', None),
            'reference': getattr(p, 'reference', None),
            'notes': getattr(p, 'notes', None),
            'allocations': alloc_by_payment.get(p.id, []),
        })

    history_out = [
        {
            'id': p['id'],
            'date': p['payment_date'],
            'amount': p['amount'],
            'method': p.get('method'),
            'reference': p.get('reference'),
            'notes': p.get('notes'),
        }
        for p in payments_out
    ]

    balance_total = 0.0
    positive_charges_count = 0
    for c in charges_out:
        try:
            if float(c.get('final_amount') or 0) > 0:
                positive_charges_count += 1
            balance_total += float(c.get('balance') or 0)
        except Exception:
            continue

    last_payment = payments[0].payment_date if payments else None

    if not charges_out or positive_charges_count == 0:
        status = 'sin_registro'
    elif overdue_total > 0:
        status = 'vencida'
    elif balance_total > 0:
        status = 'pendiente'
    else:
        status = 'al_dia'

    return {
        'student_id': student_id,
        'status': status,
        'overdue_total': round(overdue_total, 2),
        'balance_total': round(balance_total, 2),
        'last_payment': last_payment,
        'config': {
            'monthly_amount': float(cfg.monthly_amount or 0),
            'due_day': int(cfg.due_day or 10),
            'proration_mode': cfg.proration_mode or 'days',
            'proration_percent_default': float(cfg.proration_percent_default or 100),
        },
        'settings': {
            'discount_type': settings.discount_type,
            'discount_value': float(settings.discount_value or 0),
        },
        'charges': charges_out,
        'payments': payments_out,
        'history': history_out,
    }


@app.route('/api/fees/config', methods=['GET', 'PUT'])
def api_fees_config():
    cfg = _get_fee_config()
    if not cfg:
        cfg = FeeConfig(monthly_amount=0, due_day=10, proration_mode='days', proration_percent_default=100)
        db.session.add(cfg)
        db.session.commit()

    if request.method == 'GET':
        return jsonify({
            'monthly_amount': float(cfg.monthly_amount or 0),
            'due_day': int(cfg.due_day or 10),
            'proration_mode': cfg.proration_mode or 'days',
            'proration_percent_default': float(cfg.proration_percent_default or 100),
        })

    data = request.json or {}
    if 'monthly_amount' in data:
        try:
            cfg.monthly_amount = float(data.get('monthly_amount') or 0)
        except (TypeError, ValueError):
            cfg.monthly_amount = 0

    if 'due_day' in data:
        try:
            due_day = int(data.get('due_day') or 10)
        except (TypeError, ValueError):
            due_day = 10
        if due_day < 1:
            due_day = 1
        if due_day > 28:
            # Para evitar problemas con Febrero, por ahora limitamos a 28.
            due_day = 28
        cfg.due_day = due_day

    if 'proration_mode' in data:
        mode = str(data.get('proration_mode') or '').strip().lower()
        if mode in ('days', 'percent'):
            cfg.proration_mode = mode

    if 'proration_percent_default' in data:
        try:
            pct = float(data.get('proration_percent_default') or 100)
        except (TypeError, ValueError):
            pct = 100
        if pct < 0:
            pct = 0
        if pct > 100:
            pct = 100
        cfg.proration_percent_default = pct

    db.session.commit()
    return jsonify({'status': 'ok'})


@app.route('/api/fees/student/<int:student_id>', methods=['GET'])
def api_fees_student(student_id: int):
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'error': 'Alumno no encontrado'}), 404
    data = _serialize_student_fees(student_id)
    data['student'] = {
        'id': student.id,
        'full_name': student.full_name,
        'last_name': student.last_name,
        'first_name': student.first_name,
        'status': student.status,
        'belt': student.belt,
    }
    return jsonify(data)


@app.route('/api/fees/student/<int:student_id>/settings', methods=['PUT'])
def api_fees_student_settings(student_id: int):
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'error': 'Alumno no encontrado'}), 404

    settings = _get_student_fee_settings(student_id)
    data = request.json or {}
    dtype = data.get('discount_type')
    if dtype is None or dtype == '':
        settings.discount_type = None
    else:
        dtype_norm = str(dtype).strip().lower()
        if dtype_norm in ('percent', 'amount'):
            settings.discount_type = dtype_norm

    if 'discount_value' in data:
        try:
            settings.discount_value = float(data.get('discount_value') or 0)
        except Exception:
            settings.discount_value = 0

    db.session.commit()
    return jsonify({'status': 'ok'})


@app.route('/api/fees/student/<int:student_id>/charges/generate', methods=['POST'])
def api_fees_generate_charge(student_id: int):
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'error': 'Alumno no encontrado'}), 404

    cfg = _get_fee_config()
    if float(cfg.monthly_amount or 0) <= 0:
        return jsonify({'error': 'Configurá una tarifa mensual mayor a 0 antes de generar cuotas.'}), 400
    settings = _get_student_fee_settings(student_id)
    body = request.json or {}

    periods = _list_periods_from_range(body.get('period_start'), body.get('period_end'))
    if not periods:
        period_raw = body.get('period')
        if not period_raw:
            today = date.today()
            period_raw = f'{today.year:04d}-{today.month:02d}'
        period_info = _parse_period(period_raw)
        if not period_info:
            return jsonify({'error': 'Período inválido'}), 400
        periods = [period_info]

    for period_info in periods:
        _create_fee_charge(student_id, cfg, settings, period_info, body)

    db.session.commit()

    return jsonify(_serialize_student_fees(student_id))


@app.route('/api/fees/generate-month', methods=['POST'])
def api_fees_generate_month_all():
    cfg = _get_fee_config()
    if float(cfg.monthly_amount or 0) <= 0:
        return jsonify({'error': 'Configurá una tarifa mensual mayor a 0 antes de generar cuotas.'}), 400
    body = request.json or {}

    periods = _list_periods_from_range(body.get('period_start'), body.get('period_end'))
    if not periods:
        period_raw = body.get('period')
        if not period_raw:
            today = date.today()
            period_raw = f'{today.year:04d}-{today.month:02d}'
        period_info = _parse_period(period_raw)
        if not period_info:
            return jsonify({'error': 'Período inválido'}), 400
        periods = [period_info]

    created = 0
    students = Student.query.order_by(Student.id.asc()).all()
    for s in students:
        st_status = (s.status or 'activo').strip().lower()
        if st_status == 'inactivo':
            continue

        settings = _get_student_fee_settings(s.id)
        for period_info in periods:
            if _create_fee_charge(s.id, cfg, settings, period_info, body):
                created += 1

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'No se pudieron generar cuotas'}), 400

    return jsonify({'created': created})


@app.route('/api/fees/charge/<int:charge_id>', methods=['DELETE'])
def api_fees_delete_charge(charge_id: int):
    charge = FeeCharge.query.get(charge_id)
    if not charge:
        return '', 204

    allocations_count = FeeAllocation.query.filter_by(charge_id=charge.id).count()
    if allocations_count > 0:
        return jsonify({'error': 'No se puede borrar la cuota porque ya tiene pagos aplicados.'}), 400

    db.session.delete(charge)
    db.session.commit()
    return '', 204


@app.route('/api/fees/overview', methods=['GET'])
def api_fees_overview():
    _ensure_fees_tables()
    today = date.today()

    students = Student.query.order_by(
        (Student.last_name.is_(None)).asc(),
        Student.last_name.asc(),
        Student.first_name.asc(),
    ).all()

    active_students = []
    active_ids = []
    for s in students:
        st_status = (s.status or 'activo').strip().lower()
        if st_status == 'inactivo':
            continue
        active_students.append(s)
        active_ids.append(s.id)

    charges = []
    if active_ids:
        charges = FeeCharge.query.filter(FeeCharge.student_id.in_(active_ids)).all()

    charges_by_student = {}
    charge_ids = []
    for c in charges:
        charges_by_student.setdefault(c.student_id, []).append(c)
        charge_ids.append(c.id)

    allocations = []
    if charge_ids:
        allocations = FeeAllocation.query.filter(FeeAllocation.charge_id.in_(charge_ids)).all()
    paid_by_charge = {}
    for a in allocations:
        paid_by_charge[a.charge_id] = paid_by_charge.get(a.charge_id, 0.0) + float(a.amount)

    last_payments_rows = []
    if active_ids:
        last_payments_rows = (
            db.session.query(FeePayment.student_id, func.max(FeePayment.payment_date))
            .filter(FeePayment.student_id.in_(active_ids))
            .group_by(FeePayment.student_id)
            .all()
        )
    last_payment_map = {sid: pdate for (sid, pdate) in last_payments_rows}

    out = []
    for s in active_students:
        st_charges = charges_by_student.get(s.id, [])
        overdue_total = 0.0
        balance_total = 0.0
        positive_charges_count = 0
        for c in st_charges:
            total = float(c.final_amount or 0)
            if total > 0:
                positive_charges_count += 1
            paid = paid_by_charge.get(c.id, 0.0)
            balance = round(total - paid, 2)
            if balance < 0:
                balance = 0.0
            balance_total += balance
            if c.due_date and today > c.due_date and balance > 0:
                overdue_total += balance

        if not st_charges or positive_charges_count == 0:
            status = 'sin_registro'
        elif overdue_total > 0:
            status = 'vencida'
        elif balance_total > 0:
            status = 'pendiente'
        else:
            status = 'al_dia'

        out.append({
            'student_id': s.id,
            'full_name': s.full_name,
            'last_name': s.last_name,
            'first_name': s.first_name,
            'belt': s.belt,
            'status': status,
            'overdue_total': round(overdue_total, 2),
            'balance_total': round(balance_total, 2),
            'last_payment': last_payment_map.get(s.id),
        })

    return jsonify(out)


@app.route('/api/fees/student/<int:student_id>/payments', methods=['POST'])
def api_fees_register_payment(student_id: int):
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'error': 'Alumno no encontrado'}), 404

    body = request.json or {}
    payment_date = body.get('payment_date') or datetime.now().strftime('%Y-%m-%d')
    amount_raw = body.get('amount', 0)
    try:
        amount = float(amount_raw or 0)
    except Exception:
        amount = 0
    if amount < 0:
        amount = 0

    method = body.get('method') or 'cash'
    if method not in ('cash', 'transfer'):
        method = 'cash'
    reference = body.get('reference')
    notes = body.get('notes')

    payment = FeePayment(
        student_id=student_id,
        payment_date=payment_date,
        amount=round(amount, 2),
        method=method,
        reference=reference,
        notes=notes,
    )
    db.session.add(payment)
    db.session.flush()

    charge_ids = body.get('apply_to_charge_ids')
    charges_q = FeeCharge.query.filter_by(student_id=student_id)
    if isinstance(charge_ids, list) and charge_ids:
        normalized = []
        for raw in charge_ids:
            try:
                normalized.append(int(raw))
            except Exception:
                continue
        if normalized:
            charges_q = charges_q.filter(FeeCharge.id.in_(normalized))
    charges = charges_q.order_by(FeeCharge.due_date.asc()).all()

    allocated_map = _get_charge_allocated_amounts([c.id for c in charges])
    remaining_payment = round(amount, 2)

    for c in charges:
        if remaining_payment <= 0:
            break
        total = float(c.final_amount or 0)
        already = allocated_map.get(c.id, 0.0)
        remaining_charge = round(total - already, 2)
        if remaining_charge <= 0:
            continue

        applied = remaining_charge if remaining_charge < remaining_payment else remaining_payment
        if applied <= 0:
            continue

        db.session.add(FeeAllocation(payment_id=payment.id, charge_id=c.id, amount=round(applied, 2)))
        remaining_payment = round(remaining_payment - applied, 2)

    db.session.commit()
    return jsonify(_serialize_student_fees(student_id))


@app.route('/api/fees/<int:student_id>', methods=['GET', 'POST'])
def api_fees(student_id: int):
    if request.method == 'GET':
        return jsonify(_serialize_student_fees(student_id))

    payload = request.json or {}
    payload['apply_to_charge_ids'] = payload.get('apply_to_charge_ids') or []
    return api_fees_register_payment(student_id)


@app.route('/api/fees/payment/<int:payment_id>', methods=['DELETE'])
def api_fee_payment_delete(payment_id: int):
    payment = FeePayment.query.get(payment_id)
    if payment:
        FeeAllocation.query.filter_by(payment_id=payment.id).delete()
        db.session.delete(payment)
        db.session.commit()
    return '', 204


@app.route('/admin/clear-fees', methods=['GET'])
def admin_clear_fees():
    FeeAllocation.query.delete()
    FeeCharge.query.delete()
    deleted = FeePayment.query.delete()
    db.session.commit()
    return jsonify({'deleted_payments': deleted}), 200


# --- PDF generation for exam inscription ---
@app.route('/api/exams/<int:event_id>/inscription-pdf', methods=['POST'])
def generate_exam_fields_debug():
    """Genera un PDF de inscripción para un examen almacenado en la BD."""
    # Buscar el evento en la base de datos
    event = Event.query.get(event_id)
    if not event or event.type != 'exam':
        return jsonify({'error': 'Examen no encontrado'}), 404

    # (Opcional) en el futuro se podría vincular Student vía BD.
    student = None
    data = request.json or {}
    student_id = data.get('student_id')
    if student_id is not None:
        student = Student.query.get(student_id)

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Fondo simple tipo "marcial"
    p.setFillColorRGB(0, 0, 0)
    p.rect(0, 0, width, height, fill=1, stroke=0)

    # Marco blanco
    margin = 40
    p.setFillColorRGB(1, 1, 1)
    p.rect(margin, margin, width - 2 * margin, height - 2 * margin, fill=0, stroke=1)

    # Título
    p.setFillColorRGB(1, 1, 1)
    p.setFont('Helvetica-Bold', 24)
    p.drawCentredString(width / 2, height - 80, 'ESCUELA DE TAEKWONDO - ARABIA TKD')

    p.setFont('Helvetica', 14)
    p.drawCentredString(width / 2, height - 110, 'Ficha de Inscripción a Examen')

    y = height - 160
    p.setFont('Helvetica', 11)

    label_font = 'Helvetica-Bold'
    value_font = 'Helvetica'
    line_spacing = 24

    if student:
        p.setFont(label_font, 11)
        p.drawString(margin + 30, y, "Alumno:")
        p.setFont(value_font, 11)
        # Student.full_name proviene del modelo
        p.drawString(margin + 120, y, getattr(student, 'full_name', '') or '')
        y -= line_spacing

    p.setFont(label_font, 11)
    p.drawString(margin + 30, y, "Fecha de examen:")
    p.setFont(value_font, 11)
    p.drawString(margin + 150, y, f"{event.date or ''} {event.time or ''}")
    y -= line_spacing

    p.setFont(label_font, 11)
    p.drawString(margin + 30, y, "Tipo / Graduación:")
    p.setFont(value_font, 11)
    p.drawString(margin + 165, y, event.level or '')
    y -= line_spacing

    p.setFont(label_font, 11)
    p.drawString(margin + 30, y, "Lugar:")
    p.setFont(value_font, 11)
    p.drawString(margin + 90, y, event.place or '')
    y -= line_spacing

    notes = (event.notes or '').strip()
    if notes:
        p.setFont(label_font, 11)
        p.drawString(margin + 30, y, "Notas / Observaciones:")
        y -= 18
        p.setFont(value_font, 10)
        for line in notes.split('\n'):
            p.drawString(margin + 40, y, line[:90])
            y -= 14
        p.setFont(value_font, 11)

    # Frase central
    p.setFont('Helvetica-BoldOblique', 14)
    p.drawCentredString(width / 2, height / 2, '\"No falten y no lleguen tarde...\" — Master VII DAN Fernando A. Monteros')

    # Logo Arabia TKD (si existe el archivo en static/img/logo.jpg)
    logo_path = os.path.join(app.static_folder, 'img', 'logo.jpg')
    if os.path.exists(logo_path):
      try:
        logo = ImageReader(logo_path)
        logo_width = 120
        logo_height = 120
        p.drawImage(logo, width / 2 - logo_width / 2, height - 320, width=logo_width, height=logo_height, mask='auto')
      except Exception:
        # Si no se puede leer el logo, se omite silenciosamente
        pass

    p.showPage()
    p.save()

    buffer.seek(0)
    filename = f"inscripcion_examen_{event_id}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')


@app.route('/api/exams/<int:event_id>/evaluation-pdf', methods=['POST'])
def generate_exam_evaluation_pdf(event_id: int):
    """Genera un PDF de evaluación (solicitud de graduación) para un examen."""

    event = Event.query.get(event_id)
    if not event or event.type != 'exam':
        return jsonify({'error': 'Examen no encontrado'}), 404

    data = request.json or {}
    student_id = data.get('student_id')
    student = Student.query.get(student_id) if student_id is not None else None

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin = 40

    # Fondo blanco
    p.setFillColorRGB(1, 1, 1)
    p.rect(0, 0, width, height, fill=1, stroke=0)

    # Marco suave en tonos oscuros (paleta de la escuela)
    p.setStrokeColorRGB(0.1, 0.1, 0.1)
    p.setLineWidth(1.5)
    p.rect(margin, margin, width - 2 * margin, height - 2 * margin, fill=0, stroke=1)

    # Encabezado principal
    y = height - 60
    p.setFont('Helvetica-Bold', 16)
    p.setFillColorRGB(0.1, 0.1, 0.1)
    p.drawCentredString(width / 2, y, 'ESCUELA DE TAEKWON-DO ARABIA TKD')
    y -= 20

    p.setFont('Helvetica', 10)
    p.drawCentredString(width / 2, y, 'Afiliada a la Federación Argentina de Asociaciones de Taekwon-do')
    y -= 25

    p.setFont('Helvetica-Bold', 14)
    p.drawCentredString(width / 2, y, 'Solicitud de graduación')
    y -= 25

    # Fecha (ligeramente más hacia la izquierda)
    p.setFont('Helvetica', 10)
    p.drawRightString(width - margin - 20, y, f"Fecha: {event.date or ''}")
    y -= 25

    def draw_label_value(label, value, x_label, x_value):
        p.setFont('Helvetica', 10)
        p.drawString(x_label, y, label)
        p.drawString(x_value, y, value or '')

    # Datos del alumno
    full_name = ''
    birth_str = ''
    age_str = ''
    gender = ''
    address = ''
    phone = ''
    nationality = ''
    dni = ''

    if student:
        full_name = student.full_name or ''
        gender = student.gender or ''
        dni = student.dni or ''
        nationality = student.nationality or ''
        address_parts = [student.address, student.city, student.province, student.country]
        address = ' - '.join([p_ for p_ in address_parts if p_])
        phone = student.father_phone or student.mother_phone or ''

        if student.birthdate:
            birth_str = student.birthdate.strftime('%d/%m/%Y')
            today = date.today()
            age = today.year - student.birthdate.year - (
                (today.month, today.day) < (student.birthdate.month, student.birthdate.day)
            )
            age_str = str(age)

    x1 = margin + 10
    # Columna principal de valores (ligeramente más a la izquierda)
    x2 = margin + 110

    draw_label_value('Apellido y Nombre:', full_name, x1, x2)
    y -= 18
    draw_label_value('Fecha de Nacimiento:', birth_str, x1, x2)
    # Bloque derecho más hacia adentro para evitar desfasaje
    p.drawString(x2 + 80, y, 'Edad: ' + (age_str or ''))
    p.drawString(x2 + 160, y, 'Sexo: ' + (gender or ''))
    y -= 18

    draw_label_value('Domicilio:', address, x1, x2)
    y -= 18
    draw_label_value('Teléfono:', phone, x1, x2)
    p.drawString(x2 + 130, y, 'Nacionalidad: ' + (nationality or ''))
    p.drawString(x2 + 250, y, 'D.N.I: ' + (dni or ''))
    y -= 18

    draw_label_value('Ocupación:', '', x1, x2)
    p.drawString(x2 + 250, y, 'Estado civil:')
    y -= 22

    # Datos de graduación (fila más compacta para que entren las tres etiquetas)
    p.setFont('Helvetica', 10)
    p.drawString(x1, y, 'Solicita Grad.:')
    # Pequeña línea para completar
    p.drawString(x1 + 90, y, '________________')
    p.drawString(x1 + 220, y, 'Actual graduación:')
    p.drawString(x1 + 360, y, 'Tiempo de práctica:')
    y -= 18

    draw_label_value('Escuela base:', 'INSTITUTO MONTEROS DE TAEKWONDO', x1, x2)
    y -= 28

    # Instructores
    p.setFont('Helvetica-Bold', 10)
    p.drawString(x1, y, 'INSTRUCTORES')
    p.drawString(x1 + 220, y, 'Instructores auxiliares')
    y -= 14

    p.setFont('Helvetica', 10)
    p.drawString(x1, y, '- Arabia, Sirio Facundo. IV DAN')
    p.drawString(x1 + 220, y, '- Cornejo, Tomás Felipe. III DAN')
    y -= 14
    p.drawString(x1, y, '- Arabia, Farid Ignacio. IV DAN')
    p.drawString(x1 + 220, y, '- Monteros, María de los Angeles. III DAN')
    y -= 14
    p.drawString(x1, y, '- Arabia, Salma Sofia. II DAN')
    y -= 24

    # Tabla de evaluación simplificada (líneas para completar)
    p.setFont('Helvetica', 10)
    p.drawString(x1, y, 'Formas Básicas: ____________________   Téc. Patadas: ____________________')
    y -= 14
    p.drawString(x1, y, 'Sambo Matsoki: ____________________   Bolsa: ____________________')
    y -= 14
    p.drawString(x1, y, 'Ibo Matsoki:   ____________________   Bolsa: ____________________')
    y -= 14
    p.drawString(x1, y, 'Ilbo Matsoki:  ____________________   Bolsa: ____________________')
    y -= 14
    p.drawString(x1, y, 'Tul:           ____________________   Bolsa: ____________________')
    y -= 18

    p.drawString(x1, y, 'Matsoki: _____________________________________________________________')
    y -= 14
    p.drawString(x1, y, 'Defensa Personal: ____________________________________________________')
    y -= 22

    p.drawString(x1, y, 'Postura: __________  Vista: __________  Concentración: __________')
    y -= 14
    p.drawString(x1, y, 'Respiración: ______  Equilibrio: ______  Flexibilidad: ______')
    y -= 14
    p.drawString(x1, y, 'Velocidad: ________  Fuerza: ________  Agilidad: ________')
    y -= 14
    p.drawString(x1, y, 'Potencia: _________  Relajación: _________')
    y -= 18

    p.drawString(x1, y, 'Conocimiento en Oral: _______________________________________________')
    y -= 14
    p.drawString(x1, y, 'Disciplina: _______________    Teoría: ______________________________')
    y -= 18

    p.drawString(x1, y, 'Observaciones: _________________________________________________')
    y -= 28

    # Firmas (más abajo para dar aire al contenido)
    p.drawString(x1, y, 'Evaluador:')
    y -= 45
    p.line(x1, y, x1 + 200, y)
    p.drawString(x1, y - 14, 'Nombre y Firma')

    # Frase en el fondo
    p.setFont('Helvetica-Oblique', 10)
    p.drawCentredString(width / 2, margin + 20, '"No falten y no lleguen tarde…" - Master VII DAN Fernando A. Monteros')

    # Logos (si existen)
    logo_arabia_path = os.path.join(app.static_folder, 'img', 'logo.jpg')
    if os.path.exists(logo_arabia_path):
        try:
            logo = ImageReader(logo_arabia_path)
            # Esquina superior derecha dentro del marco
            logo_width = 80
            logo_height = 80
            p.drawImage(logo, width - margin - logo_width, height - margin - logo_height, width=logo_width, height=logo_height, mask='auto')
        except Exception:
            pass
    logo_monteros_path = os.path.join(app.static_folder, 'img', 'logo_monteros.png')
    if os.path.exists(logo_monteros_path):
        try:
            logo2 = ImageReader(logo_monteros_path)
            p.drawImage(logo2, width - margin - 90, height - 170, width=80, height=80, mask='auto')
        except Exception:
            pass

    p.showPage()
    p.save()

    buffer.seek(0)
    filename = f"evaluacion_examen_{event_id}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')


@app.route('/api/exams/<int:event_id>/rinde-pdf', methods=['POST'])
def generate_exam_rinde_pdf(event_id: int):
    """Genera un PDF de rendida multi-hoja usando el PDF base de Taekwondo.

    Cada alumno va en una página distinta, partiendo de la primera página del
    archivo 'src/PDF TAEKWONDO - ultima edición.pdf'.
    """

    event = Event.query.get(event_id)
    if not event or event.type != 'exam':
        return jsonify({'error': 'Examen no encontrado'}), 404

    data = request.json or {}
    raw_ids = data.get('student_ids') or []

    # Normalizar a enteros válidos
    student_ids = []
    for raw in raw_ids:
        try:
            student_ids.append(int(raw))
        except (TypeError, ValueError):
            continue

    if not student_ids:
        return jsonify({'error': 'No se recibieron alumnos para el examen'}), 400

    students = Student.query.filter(Student.id.in_(student_ids)).all()
    if not students:
        return jsonify({'error': 'Alumnos no encontrados'}), 404

    # Ordenar alumnos alfabéticamente por Apellido, Nombre (o full_name como fallback)
    def _student_sort_key(st: Student):
        ln = (st.last_name or '').strip().lower()
        fn = (st.first_name or '').strip().lower()
        full = (st.full_name or '').strip().lower()
        # Si no hay last/first, usamos full_name
        if ln or fn:
            return (ln, fn)
        return (full or '', '')

    students.sort(key=_student_sort_key)

    # Progresión de cinturones, Gup y Graduación (igual que en el frontend)
    belt_progress = [
        {"belt": "Blanco", "gup": "10º Gup", "graduation": "Primera"},
        {"belt": "Blanco Punta Amarilla", "gup": "9º Gup", "graduation": "Segunda"},
        {"belt": "Amarillo", "gup": "8º Gup", "graduation": "Tercera"},
        {"belt": "Amarillo Punta Verde", "gup": "7º Gup", "graduation": "Cuarta"},
        {"belt": "Verde", "gup": "6º Gup", "graduation": "Quinta"},
        {"belt": "Verde Punta Azul", "gup": "5º Gup", "graduation": "Sexta"},
        {"belt": "Azul", "gup": "4º Gup", "graduation": "Séptima"},
        {"belt": "Azul Punta Roja", "gup": "3º Gup", "graduation": "Octava"},
        {"belt": "Rojo", "gup": "2º Gup", "graduation": "Novena"},
        {"belt": "Rojo Punta Negra", "gup": "1º Gup", "graduation": "Décima"},
        {"belt": "Negro Primer Dan", "gup": "", "graduation": "Primer Dan"},
        {"belt": "Segundo Dan", "gup": "", "graduation": "Segundo Dan"},
    ]

    def get_belt_infos(current_belt: str):
        """Devuelve (info_actual, info_siguiente) según la progresión de cinturones."""
        if not current_belt:
            return None, None
        current = current_belt.strip().lower()
        idx = next((i for i, b in enumerate(belt_progress) if b["belt"].lower() == current), -1)
        if idx == -1:
            return None, None
        current_info = belt_progress[idx]
        next_info = belt_progress[idx + 1] if idx < len(belt_progress) - 1 else None
        return current_info, next_info

    # Cargar PDF base
    template_path = os.path.join('src', 'PDF TAEKWONDO - ultima edición.pdf')
    if not os.path.exists(template_path):
        return jsonify({'error': 'PDF base no encontrado en src'}), 500

    reader = PdfReader(template_path)
    if not reader.pages:
        return jsonify({'error': 'PDF base sin páginas'}), 500

    template_page = reader.pages[0]
    page_width = float(template_page.mediabox.width)
    page_height = float(template_page.mediabox.height)

    writer = PdfWriter()

    for student in students:
        # Datos del alumno
        if student.last_name or student.first_name:
            # Formato "Apellido, Nombre" cuando hay ambos
            if student.last_name and student.first_name:
                full_name = f"{student.last_name}, {student.first_name}"
            else:
                full_name = (student.last_name or student.first_name) or ''
        else:
            full_name = student.full_name or ''
        dni = student.dni or ''
        gender = (student.gender or '').upper()
        belt_current = (student.belt or '').strip()
        current_info, next_info = get_belt_infos(belt_current)
        belt_next = next_info["belt"] if next_info else ''
        gup_current = current_info["gup"] if current_info else ''
        gup_next = next_info["gup"] if next_info else ''

        # Fecha de nacimiento y edad (en años y meses)
        birth_str = ''
        age_str = ''
        if student.birthdate:
            birth_str = student.birthdate.strftime('%d/%m/%Y')
            try:
                exam_date = datetime.strptime(event.date, '%Y-%m-%d').date() if event.date else date.today()
            except ValueError:
                exam_date = date.today()

            years = exam_date.year - student.birthdate.year
            months = exam_date.month - student.birthdate.month
            days = exam_date.day - student.birthdate.day

            # Ajuste por días: si los días son negativos, restamos un mes
            if days < 0:
                months -= 1

            # Ajuste por meses negativos
            if months < 0:
                years -= 1
                months += 12

            if years < 0:
                years = 0
            if months < 0:
                months = 0

            age_str = f"{years} años y {months} meses"

        # Fecha de examen en formato DD/MM/AAAA si es posible
        fecha_examen = ''
        if event.date:
            try:
                _exam_dt = datetime.strptime(event.date, '%Y-%m-%d').date()
                fecha_examen = _exam_dt.strftime('%d/%m/%Y')
            except ValueError:
                fecha_examen = event.date

        # Coordinadas base (similares a las del PDF de debug)
        # x_left ligeramente más a la derecha para ajustar el nombre
        x_left = page_width * 0.265
        # Columna derecha superior (Fecha/DNI/Edad) más a la derecha
        x_right_top = page_width * 0.78
        # Columna derecha media en una posición fija razonable
        x_right_mid = page_width * 0.52

        # y_start_left un poco más arriba para terminar de ajustar la altura del nombre
        y_start_left = page_height - 146
        # Columna derecha superior aún más arriba para la Fecha de examen
        y_start_right_top = page_height - 160
        # Columna derecha media más arriba
        y_start_right_mid = page_height - 200
        step = 14

        # Crear overlay con ReportLab (solo datos variables, sin modificar el título original del formulario)
        overlay_buf = BytesIO()
        c = canvas.Canvas(overlay_buf, pagesize=(page_width, page_height))
        c.setFont('Helvetica', 9)

        # Columna izquierda (Nombre, Sexo, Cinturón actual, GUP actual)
        y = y_start_left
        c.drawString(x_left, y, full_name or '')         # Apellido y Nombre
        y -= step
        # Sexo un poquito más a la izquierda y apenas más arriba
        c.drawString(x_left - 65, y - 1, gender or '')   # Sexo
        y -= step
        # Cinturón actual un poquito más a la izquierda y un poquito más abajo
        c.drawString(x_left - 14, y - 1, belt_current or '')  # Cinturón actual
        y -= step
        # GUP actual un poquito más a la izquierda y un poquito más abajo
        c.drawString(x_left - 34, y - 2, gup_current or '')  # GUP actual

        # Columna derecha superior (Fecha examen, DNI, Edad)
        y_rt = y_start_right_top
        # Fecha de examen un poquito más arriba y un poco más a la izquierda
        c.drawString(x_right_top - 15, y_rt + 44, fecha_examen or '')  # Fecha examen
        y_rt -= step
        # DNI alineado en X con la Fecha de examen, apenas más arriba y un poco más a la izquierda
        c.drawString(x_right_top - 17, y_rt + 27, dni or '')           # DNI
        y_rt -= step
        # Edad alineada en X con DNI, un poquito más abajo y un poquito más a la izquierda
        c.drawString(x_right_top - 18, y_rt + 27, age_str or '')       # Edad

        # Columna derecha media (Fecha nacimiento, Cinturón que rinde, GUP que rinde)
        y_rm = y_start_right_mid
        # Subimos Fecha de nacimiento para que esté a la altura aproximada de Sexo
        # y la movemos muy ligeramente más hacia la izquierda (ajuste muy fino)
        c.drawString(x_right_mid + 31, y_rm + 39, birth_str or '')     # Fecha nacimiento
        y_rm -= step
        # Cinturón que rinde (Solicita cinturón) bastante más a la izquierda dentro de la columna
        c.drawString(x_right_mid + 10, y_rm + 38, belt_next or '')     # Cinturón que rinde
        y_rm -= step
        # GUP que rinde (Solicita GUP) medio punto más arriba y un poquito a la izquierda
        c.drawString(x_right_mid - 5, y_rm + 38, gup_next or '') # GUP que rinde

        c.showPage()
        c.save()

        overlay_buf.seek(0)
        overlay_reader = PdfReader(overlay_buf)
        overlay_page = overlay_reader.pages[0]

        merged_page = PageObject.create_blank_page(
            width=template_page.mediabox.width,
            height=template_page.mediabox.height,
        )
        merged_page.merge_page(template_page)
        merged_page.merge_page(overlay_page)
        writer.add_page(merged_page)

    out_buffer = BytesIO()
    writer.write(out_buffer)
    out_buffer.seek(0)

    # Usar la fecha del examen en el nombre del archivo como DD-MM-AAAA (sin barras, para que sea válido)
    if event.date:
        try:
            _exam_dt = datetime.strptime(event.date, '%Y-%m-%d').date()
            date_for_name = _exam_dt.strftime('%d-%m-%Y')
        except ValueError:
            date_for_name = event.date.replace('/', '-').replace(' ', '_')
    else:
        date_for_name = 'sin_fecha'

    # Incluir el lugar del examen en el nombre del archivo (por ejemplo, el gimnasio o sede)
    raw_place = event.place or 'Taekwondo'
    # Normalizar un poco el lugar para usarlo en un nombre de archivo
    place_slug = ''.join(ch if ch.isalnum() or ch in (' ', '-', '_') else ' ' for ch in raw_place)
    place_slug = '_'.join(part for part in place_slug.split() if part)

    filename = f"Examen_{place_slug}_{date_for_name}.pdf"
    # Debug: ver en consola qué nombre de archivo está usando realmente el backend
    print(f"[generate_exam_rinde_pdf] filename= {filename}")
    return send_file(out_buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')


@app.route('/api/exams/template-debug-pdf', methods=['GET'])
def exam_template_debug_pdf():
  """Genera un PDF de calibración con marcadores L1..L12 y R1..R12 sobre la plantilla base.

  Usar este PDF para identificar qué marcador coincide con cada línea amarilla
  del formulario y así ajustar con precisión las coordenadas.
  """

  template_path = os.path.join('src', 'PDF TAEKWONDO - ultima edición.pdf')
  if not os.path.exists(template_path):
      return jsonify({'error': 'PDF base no encontrado en src'}), 500

  reader = PdfReader(template_path)
  if not reader.pages:
      return jsonify({'error': 'PDF base sin páginas'}), 500
  template_page = reader.pages[0]

  writer = PdfWriter()

  # Usamos el tamaño real de la página de la plantilla para que overlay y base coincidan 1:1
  overlay_width = float(template_page.mediabox.width)
  overlay_height = float(template_page.mediabox.height)
  x_left = overlay_width * 0.30
  x_right_top = overlay_width * 0.72
  x_right_mid = overlay_width * 0.63

  buf_overlay = BytesIO()
  c = canvas.Canvas(buf_overlay, pagesize=(overlay_width, overlay_height))
  c.setFont('Helvetica', 8)

  # Marcadores L1..L12 en la columna izquierda.
  # Subimos el bloque para que L1 quede a la altura de "Apellido y Nombre".
  y_start_left = overlay_height - 180
  step = 14
  for i in range(12):
      y = y_start_left - i * step
      c.drawString(x_left, y, f'L{i + 1}')

  # Marcadores R1..R12 en la columna derecha superior (Fecha/DNI/Edad)
  y_start_right_top = overlay_height - 220
  for i in range(12):
      y = y_start_right_top - i * step
      c.drawString(x_right_top, y, f'RT{i + 1}')

  # Marcadores RM1..RM12 en la columna derecha media (Fecha Nac / Solicita cinturón / Solicita GUP)
  y_start_right_mid = overlay_height - 260
  for i in range(12):
      y = y_start_right_mid - i * step
      c.drawString(x_right_mid, y, f'RM{i + 1}')

  c.save()
  buf_overlay.seek(0)

  overlay_reader = PdfReader(buf_overlay)
  overlay_page = overlay_reader.pages[0]

  merged_page = PageObject.create_blank_page(
      width=template_page.mediabox.width,
      height=template_page.mediabox.height,
  )
  merged_page.merge_page(template_page)
  merged_page.merge_page(overlay_page)
  writer.add_page(merged_page)

  out_buffer = BytesIO()
  writer.write(out_buffer)
  out_buffer.seek(0)

  return send_file(out_buffer, as_attachment=True, download_name='debug_examen_template.pdf', mimetype='application/pdf')


@app.route('/api/exams/template-fields', methods=['GET'])
def exam_template_fields():
    """Devuelve los campos de formulario (AcroForm) del PDF base.

    Útil para ver exactamente cómo se llaman los campos de texto que creaste
    en la plantilla editable y poder mapearlos desde el backend.
    """

    template_path = os.path.join('src', 'PDF TAEKWONDO - ultima edición.pdf')
    if not os.path.exists(template_path):
        return jsonify({'error': 'PDF base no encontrado en src'}), 500

    reader = PdfReader(template_path)
    if not reader.pages:
        return jsonify({'error': 'PDF base sin páginas'}), 500

    fields = reader.get_fields() or {}
    # Convertimos los objetos de PyPDF2 a strings simples
    simple = {}
    for name, data in fields.items():
        simple[str(name)] = {
            'name': str(name),
            'type': str(data.get('/FT')) if isinstance(data, dict) else None,
        }

    return jsonify(simple)


def _startup_init_db():
    try:
        with app.app_context():
            db.create_all()
    except Exception:
        pass


_startup_init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    dbg = os.environ.get('FLASK_DEBUG') or os.environ.get('DEBUG')
    debug = False
    if dbg is not None and str(dbg).strip() != '':
        debug = str(dbg).strip().lower() in ('1', 'true', 'yes', 'y', 'on')
    else:
        debug = os.environ.get('DATABASE_URL') is None

    app.run(host='0.0.0.0', port=port, debug=debug)
