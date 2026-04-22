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
                    'discount_type': 'TEXT',
                    'discount_value': 'NUMERIC(10, 2) DEFAULT 0',
                    'surcharge_type': 'TEXT',
                    'surcharge_value': 'NUMERIC(10, 2) DEFAULT 0',
                }
                for column_name, column_def in payment_column_defs.items():
                    if column_name not in payment_columns:
                        conn.execute(text(f"ALTER TABLE fee_payments ADD COLUMN {column_name} {column_def}"))
    except Exception:
        pass
    
    # Asegurar columna is_active en students
    try:
        with db.engine.begin() as conn:
            inspector = inspect(conn)
            if 'students' in inspector.get_table_names():
                student_columns = {col['name'] for col in inspector.get_columns('students')}
                if 'is_active' not in student_columns:
                    # PostgreSQL requiere DEFAULT TRUE (no DEFAULT 1)
                    conn.execute(text("ALTER TABLE students ADD COLUMN is_active BOOLEAN DEFAULT TRUE"))
                    print("[MIGRATION] Columna is_active agregada a students con DEFAULT TRUE")
    except Exception as e:
        print(f"[MIGRATION ERROR] No se pudo agregar is_active: {e}")

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
    is_active = db.Column(db.Boolean, default=True)  # Control para sistema de cuotas
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
    discount_type = db.Column(db.String(20))  # 'percent' | 'fixed' | None
    discount_value = db.Column(db.Numeric(10, 2), default=0)
    surcharge_type = db.Column(db.String(20))  # 'percent' | 'fixed' | None
    surcharge_value = db.Column(db.Numeric(10, 2), default=0)
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


class FeeMonthlyValue(db.Model):
    __tablename__ = "fee_monthly_values"

    period = db.Column(db.String(7), primary_key=True)  # YYYY-MM
    monthly_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StudentFeeSettings(db.Model):
    __tablename__ = "student_fee_settings"

    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), primary_key=True)
    discount_type = db.Column(db.String(20))  # 'percent' | 'amount'
    discount_value = db.Column(db.Numeric(10, 2), nullable=False, default=0)


class StudentStatusHistory(db.Model):
    __tablename__ = "student_status_history"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    effective_period = db.Column(db.String(7), nullable=False)  # YYYY-MM desde cuando aplica
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.Index('idx_student_status_period', 'student_id', 'effective_period'),
    )


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
        _ensure_fees_tables()
        today = date.today()
        current_period = f'{today.year:04d}-{today.month:02d}'

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
            is_active_current_period = _get_student_status_for_period(s.id, current_period)
            result.append({
                'id': s.id,
                'full_name': s.full_name,
                'last_name': s.last_name,
                'first_name': s.first_name,
                'dni': s.dni,
                'gender': s.gender,
                'birthdate': s.birthdate.isoformat() if s.birthdate else None,
                'blood': s.blood,
                'is_active': is_active_current_period,
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
                'status': 'activo' if is_active_current_period else 'inactivo',
                'tutor_type': s.tutor_type,
                'status_period': current_period,
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


@app.route('/api/students/<int:student_id>/toggle-active', methods=['PUT'])
def api_student_toggle_active(student_id: int):
    student = db.session.get(Student, student_id)
    if not student:
        return jsonify({'error': 'Alumno no encontrado'}), 404
    
    # Estado Activo/Inactivo estrictamente por período (sin arrastre a otros meses)
    data = request.json or {}
    effective_period = data.get('period', '').strip()
    
    if not effective_period:
        # Si no se especifica período, usar el mes actual
        today = date.today()
        effective_period = f'{today.year:04d}-{today.month:02d}'

    if not _parse_period(effective_period):
        return jsonify({'error': 'Período inválido. Usá formato YYYY-MM.'}), 400
    
    # Toggle del estado mensual para el período seleccionado (no global)
    current_active = _get_student_status_for_period(student_id, effective_period)
    new_active = not current_active
    
    # Registrar cambio solo para el período seleccionado
    _set_student_status_from_period(student_id, effective_period, new_active)
    
    return jsonify({'id': student.id, 'is_active': new_active, 'effective_period': effective_period})


@app.route('/api/students/<int:student_id>', methods=['GET', 'PUT', 'DELETE'])
def api_student_detail(student_id: int):
    student = db.session.get(Student, student_id)
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
        status_is_active_for_current_period = None
        for field in [
            'full_name', 'last_name', 'first_name', 'dni', 'gender', 'blood',
            'nationality', 'province', 'country', 'city', 'address', 'zip',
            'school', 'belt', 'father_name', 'mother_name', 'father_phone',
            'mother_phone', 'parent_email', 'notes', 'tutor_type',
        ]:
            if field in data:
                setattr(student, field, data[field])

        if 'status' in data:
            status_raw = str(data.get('status') or '').strip().lower()
            if status_raw in ('activo', 'inactivo'):
                student.status = status_raw
                status_is_active_for_current_period = (status_raw == 'activo')

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

        if status_is_active_for_current_period is not None:
            today = date.today()
            current_period = f'{today.year:04d}-{today.month:02d}'
            _set_student_status_from_period(student_id, current_period, status_is_active_for_current_period)
        else:
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
    event = db.session.get(Event, event_id)
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

    event = db.session.get(Event, event_id)
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
        cfg = FeeConfig(monthly_amount=0, due_day=1, proration_mode='percent', proration_percent_default=100)
        db.session.add(cfg)
        db.session.commit()
    if int(cfg.due_day or 1) != 1 or (cfg.proration_mode or 'percent') != 'percent' or float(cfg.proration_percent_default or 100) != 100:
        cfg.due_day = 1
        cfg.proration_mode = 'percent'
        cfg.proration_percent_default = 100
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


def _get_student_status_for_period(student_id: int, period: str) -> bool:
    """
    Obtiene el estado activo/inactivo del alumno para un período específico (exacto).
    Si no hay registro para ese período, se considera activo por defecto.
    """
    _ensure_fees_tables()
    student = db.session.get(Student, student_id)
    if not student:
        return False
    
    # Buscar estado EXACTO del período (sin herencia a meses siguientes).
    status_record = (
        StudentStatusHistory.query
        .filter_by(student_id=student_id, effective_period=period)
        .first()
    )
    
    if status_record:
        return status_record.is_active
    
    # Si no hay historial para ese mes, por defecto activo.
    return True


def _set_student_status_from_period(student_id: int, period: str, is_active: bool):
    """
    Registra un cambio de estado del alumno para un período específico.
    Si ya existe un registro para ese período exacto, lo actualiza.
    Si no, crea uno nuevo.
    """
    _ensure_fees_tables()
    
    existing = (
        StudentStatusHistory.query
        .filter_by(student_id=student_id, effective_period=period)
        .first()
    )
    
    if existing:
        existing.is_active = is_active
    else:
        new_record = StudentStatusHistory(
            student_id=student_id,
            effective_period=period,
            is_active=is_active
        )
        db.session.add(new_record)
    
    db.session.commit()


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
    
    # Si ya existe, NO actualizar (valor solo hacia adelante)
    if existing:
        return False
    
    # Obtener valor del período específico si existe, sino usar global
    period_value = FeeMonthlyValue.query.filter_by(period=period_info['period']).first()
    base_amount = float(period_value.monthly_amount if period_value else cfg.monthly_amount or 0)
    
    if base_amount <= 0:
        return False
    
    # CORRECCIÓN CRÍTICA: NO aplicar descuentos permanentes en la cuota base
    # Todos los alumnos del período deben tener el mismo valor base
    # Los descuentos se aplican solo en el momento del pago
    final_amount = round(base_amount, 2)

    year = period_info['year']
    month = period_info['month']
    due_date = date(year, month, 1)

    charge = FeeCharge(
        student_id=student_id,
        period=period_info['period'],
        due_date=due_date,
        base_amount=round(base_amount, 2),
        discount_amount=0.00,  # Sin descuentos en la cuota base
        proration_mode='percent',
        proration_percent=100,
        proration_start_date=None,
        final_amount=final_amount,  # Valor exacto del período
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
    if dtype == 'fixed':
        if dval > base_amount:
            dval = base_amount
        discount = base_amount - dval
    elif dtype == 'percent':
        discount = base_amount * (dval / 100.0)
    elif dtype == 'amount':
        discount = dval
    else:
        discount = 0
    if discount > base_amount:
        discount = base_amount
    return round(discount, 2)


def _update_period_charges_with_new_rate(period: str, new_monthly_amount: float):
    """
    Actualiza las cuotas pendientes (no pagadas completamente) de un período específico
    con la nueva tarifa mensual.
    
    Solo actualiza cuotas que tienen saldo pendiente.
    No toca cuotas completamente pagadas para preservar el historial.
    """
    if new_monthly_amount <= 0:
        return
    
    # Obtener todas las cuotas del período
    period_charges = FeeCharge.query.filter_by(period=period).all()
    
    if not period_charges:
        return
    
    # Obtener allocations para saber cuánto se pagó de cada cuota
    charge_ids = [c.id for c in period_charges]
    allocations = FeeAllocation.query.filter(FeeAllocation.charge_id.in_(charge_ids)).all()
    
    paid_by_charge = {}
    for a in allocations:
        paid_by_charge[a.charge_id] = paid_by_charge.get(a.charge_id, 0.0) + float(a.amount)
    
    # Actualizar solo cuotas con saldo pendiente
    for charge in period_charges:
        paid_amount = paid_by_charge.get(charge.id, 0.0)
        old_final = float(charge.final_amount or 0)
        
        # Si la cuota está completamente pagada, no tocarla (preservar historial)
        if paid_amount >= old_final and old_final > 0:
            continue
        
        # CORRECCIÓN CRÍTICA: Actualizar al valor exacto del período sin descuentos
        # Todos los alumnos del período deben tener el mismo valor base
        # Los descuentos se aplican solo en el momento del pago, no en la cuota base
        charge.base_amount = round(new_monthly_amount, 2)
        charge.discount_amount = 0.00  # Sin descuentos en la cuota base
        charge.final_amount = round(new_monthly_amount, 2)  # Valor exacto del período
    
    db.session.commit()


def _refresh_student_fee_charges(student_id: int, cfg: FeeConfig, settings: StudentFeeSettings):
    charges = FeeCharge.query.filter_by(student_id=student_id).all()
    base_amount = float(cfg.monthly_amount or 0)
    if base_amount <= 0:
        return

    discount_amount = _compute_discount_amount(base_amount, settings)
    final_amount = round(max(base_amount - discount_amount, 0), 2)

    for charge in charges:
        period_info = _parse_period(charge.period)
        if not period_info:
            continue
        charge.base_amount = round(base_amount, 2)
        charge.discount_amount = round(discount_amount, 2)
        charge.proration_mode = 'percent'
        charge.proration_percent = 100
        charge.proration_start_date = None
        charge.due_date = date(period_info['year'], period_info['month'], 1)
        charge.final_amount = final_amount


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


def _calculate_payment_adjustments(payment, allocations):
    """
    Calcula descuentos y recargos reales aplicados por un pago.
    Retorna (subtotal_original, descuento_total, recargo_total).
    
    Lógica:
    - amount es el total FINAL pagado
    - Necesitamos calcular el subtotal ANTES de desc/rec
    - descuento reduce la deuda
    - recargo aumenta la deuda
    """
    amount = float(payment.amount or 0)
    discount_type = payment.discount_type
    discount_value = float(payment.discount_value or 0)
    surcharge_type = payment.surcharge_type
    surcharge_value = float(payment.surcharge_value or 0)
    
    # Calcular subtotal trabajando hacia atrás desde amount
    if discount_type == 'percent' and discount_value > 0:
        # amount = subtotal * (1 - disc%) + recargo
        if surcharge_type == 'fixed':
            subtotal_after_discount = amount - surcharge_value
            if discount_value < 100:
                subtotal = subtotal_after_discount / (1 - discount_value / 100)
            else:
                subtotal = 0
            discount_amt = subtotal * (discount_value / 100)
            surcharge_amt = surcharge_value
        elif surcharge_type == 'percent':
            # Complejo: amount = subtotal * (1 - disc%) * (1 + rec%)
            # Simplificamos: usamos amount como base
            subtotal = amount
            discount_amt = 0
            surcharge_amt = 0
        else:
            # Solo descuento porcentual
            if discount_value < 100:
                subtotal = amount / (1 - discount_value / 100)
            else:
                subtotal = 0
            discount_amt = subtotal * (discount_value / 100)
            surcharge_amt = 0
    elif discount_type == 'fixed' and discount_value > 0:
        # amount = subtotal - discount + recargo
        if surcharge_type == 'percent':
            # (subtotal - disc) * (1 + rec%) = amount
            if surcharge_value > -100:
                subtotal_after_discount = amount / (1 + surcharge_value / 100)
            else:
                subtotal_after_discount = 0
            subtotal = subtotal_after_discount + discount_value
            discount_amt = discount_value
            surcharge_amt = subtotal_after_discount * (surcharge_value / 100)
        elif surcharge_type == 'fixed':
            # subtotal - disc + rec = amount
            subtotal = amount + discount_value - surcharge_value
            discount_amt = discount_value
            surcharge_amt = surcharge_value
        else:
            # Solo descuento fijo
            subtotal = amount + discount_value
            discount_amt = discount_value
            surcharge_amt = 0
    else:
        # Sin descuento
        if surcharge_type == 'percent' and surcharge_value > 0:
            # subtotal * (1 + rec%) = amount
            if surcharge_value > -100:
                subtotal = amount / (1 + surcharge_value / 100)
            else:
                subtotal = 0
            discount_amt = 0
            surcharge_amt = subtotal * (surcharge_value / 100)
        elif surcharge_type == 'fixed' and surcharge_value > 0:
            # subtotal + rec = amount
            subtotal = amount - surcharge_value
            discount_amt = 0
            surcharge_amt = surcharge_value
        else:
            # Sin ajustes
            subtotal = amount
            discount_amt = 0
            surcharge_amt = 0
    
    return (round(subtotal, 2), round(discount_amt, 2), round(surcharge_amt, 2))


def _get_charge_adjustments_from_payments(charge_ids, student_id):
    """
    Calcula los descuentos y recargos aplicados a cada cuota desde los pagos.
    Retorna dict: {charge_id: {'discount': X, 'surcharge': Y}}
    
    Lógica:
    - Por cada pago que afecta una cuota, distribuir desc/rec proporcionalmente
    - Si un pago cubre múltiples cuotas, el desc/rec se reparte según el monto asignado
    """
    if not charge_ids:
        return {}
    
    # Obtener todos los pagos del estudiante
    payments = FeePayment.query.filter_by(student_id=student_id).all()
    if not payments:
        return {}
    
    # Obtener allocations que afectan estas cuotas
    allocations = FeeAllocation.query.filter(
        FeeAllocation.charge_id.in_(charge_ids)
    ).all()
    
    # Agrupar allocations por payment_id
    allocs_by_payment = {}
    for a in allocations:
        allocs_by_payment.setdefault(a.payment_id, []).append(a)
    
    # Calcular ajustes por cuota
    charge_adjustments = {cid: {'discount': 0.0, 'surcharge': 0.0} for cid in charge_ids}
    
    for payment in payments:
        if payment.id not in allocs_by_payment:
            continue
        
        # Calcular desc/rec totales de este pago
        subtotal, discount_total, surcharge_total = _calculate_payment_adjustments(payment, allocs_by_payment[payment.id])
        
        if discount_total == 0 and surcharge_total == 0:
            continue
        
        # Distribuir proporcionalmente según monto asignado a cada cuota
        payment_allocs = allocs_by_payment[payment.id]
        total_allocated = sum(float(a.amount) for a in payment_allocs)
        
        if total_allocated <= 0:
            continue
        
        for alloc in payment_allocs:
            if alloc.charge_id not in charge_adjustments:
                continue
            
            proportion = float(alloc.amount) / total_allocated
            charge_adjustments[alloc.charge_id]['discount'] += round(discount_total * proportion, 2)
            charge_adjustments[alloc.charge_id]['surcharge'] += round(surcharge_total * proportion, 2)
    
    return charge_adjustments


def _build_charge_financials(charges, allocated_map, student_credit=0.0, today_value=None, charge_adjustments=None):
    """
    Calcula el estado financiero de cada cuota.
    
    Lógica corregida:
    - total_final_cuota = final_amount - descuento_aplicado + recargo_aplicado
    - saldo = total_final_cuota - monto_pagado
    - Si saldo <= 0, cuota está SALDADA
    """
    today_value = today_value or date.today()
    remaining_credit = round(float(student_credit or 0), 2)
    charge_meta = {}
    charge_adjustments = charge_adjustments or {}

    ordered = sorted(
        charges,
        key=lambda c: (
            c.due_date or date.max,
            c.period or '',
            c.id or 0,
        )
    )

    for c in ordered:
        paid = round(float(allocated_map.get(c.id, 0.0)), 2)
        base_total = round(float(c.final_amount or 0), 2)
        
        # Obtener descuentos y recargos aplicados a esta cuota desde pagos
        adjustments = charge_adjustments.get(c.id, {'discount': 0.0, 'surcharge': 0.0})
        discount_applied = round(float(adjustments.get('discount', 0.0)), 2)
        surcharge_applied = round(float(adjustments.get('surcharge', 0.0)), 2)
        
        # LÓGICA CORRECTA: total_final = base - descuento + recargo
        total = round(base_total - discount_applied + surcharge_applied, 2)
        
        # Saldo = total_final - pagado
        raw_balance = round(total - paid, 2)
        applied_credit = 0.0
        if raw_balance > 0 and remaining_credit > 0:
            applied_credit = min(raw_balance, remaining_credit)
            remaining_credit = round(remaining_credit - applied_credit, 2)

        effective_balance = round(raw_balance - applied_credit, 2)
        outstanding_balance = max(0.0, effective_balance)
        credit_amount = abs(min(0.0, effective_balance))

        # LÓGICA CORRECTA DE ESTADO:
        # Si saldo efectivo <= 0, la cuota está SALDADA
        if effective_balance <= 0 and base_total > 0:
            status = 'paid'
        elif paid > 0 or discount_applied > 0:
            status = 'partial'
        else:
            status = 'pending'

        is_overdue = (c.due_date is not None) and (today_value > c.due_date) and (status != 'paid')
        charge_meta[c.id] = {
            'paid': paid,
            'base_total': base_total,
            'discount_applied': discount_applied,
            'surcharge_applied': surcharge_applied,
            'total': total,
            'applied_credit': round(applied_credit, 2),
            'balance': round(effective_balance, 2),
            'outstanding_balance': round(outstanding_balance, 2),
            'credit_amount': round(credit_amount, 2),
            'status': status,
            'overdue': is_overdue,
        }

    overdue_total = 0.0
    credit_total = round(remaining_credit, 2)
    has_partial = False
    balance_total = 0.0
    positive_charges_count = 0
    for c in charges:
        meta = charge_meta.get(c.id, {})
        total = float(meta.get('total', 0.0))
        if total > 0:
            positive_charges_count += 1
        balance_total += float(meta.get('balance', 0.0))
        if meta.get('overdue') and float(meta.get('outstanding_balance', 0.0)) > 0:
            overdue_total += float(meta.get('outstanding_balance', 0.0))
        credit_total += float(meta.get('credit_amount', 0.0))
        if meta.get('status') == 'partial' and float(meta.get('outstanding_balance', 0.0)) > 0:
            has_partial = True

    return {
        'by_charge_id': charge_meta,
        'overdue_total': round(overdue_total, 2),
        'credit_total': round(credit_total, 2),
        'has_partial': has_partial,
        'balance_total': round(balance_total - remaining_credit, 2),
        'positive_charges_count': positive_charges_count,
        'remaining_credit': round(remaining_credit, 2),
    }


def _serialize_student_fees(student_id: int, target_period: str = None):
    """
    Serializa las cuotas y pagos de un alumno.
    Si target_period se especifica (formato YYYY-MM), genera cuota solo para ese período.
    Si no se especifica, genera cuota para el mes actual.
    """
    _ensure_fees_tables()
    cfg = _get_fee_config()
    settings = _get_student_fee_settings(student_id)
    today = date.today()
    
    # Determinar el período para el cual generar cuota
    if target_period:
        period_to_generate = target_period
    else:
        period_to_generate = f'{today.year:04d}-{today.month:02d}'
    
    # Generar cuota del período especificado si no existe y el alumno estaba activo en ese período
    student = db.session.get(Student, student_id)
    if student:
        is_active_in_period = _get_student_status_for_period(student_id, period_to_generate)
        if is_active_in_period:
            period_info = _parse_period(period_to_generate)
            if period_info:
                existing_charge = FeeCharge.query.filter_by(student_id=student_id, period=period_to_generate).first()
                if not existing_charge:
                    # Generar cuota del período especificado automáticamente
                    _create_fee_charge(student_id, cfg, settings, period_info, {})
                    db.session.commit()

    charges = FeeCharge.query.filter_by(student_id=student_id).order_by(FeeCharge.period.desc()).all()
    payments = FeePayment.query.filter_by(student_id=student_id).order_by(FeePayment.payment_date.desc(), FeePayment.id.desc()).all()
    charge_ids = [c.id for c in charges]
    allocated_map = _get_charge_allocated_amounts(charge_ids)
    
    # IMPORTANTE:
    # Cuando se consulta un período específico, la cuota del período debe respetar
    # su valor base oficial (tarifa mensual del período), sin arrastrar ajustes
    # históricos de otros pagos.
    if target_period:
        charge_adjustments = {}
    else:
        charge_adjustments = _get_charge_adjustments_from_payments(charge_ids, student_id)
    
    payment_ids = [p.id for p in payments]
    allocations = []
    if payment_ids:
        allocations = FeeAllocation.query.filter(FeeAllocation.payment_id.in_(payment_ids)).all()
    allocated_by_payment = {}
    alloc_by_payment = {}
    for a in allocations:
        allocated_by_payment[a.payment_id] = allocated_by_payment.get(a.payment_id, 0.0) + float(a.amount)
        alloc_by_payment.setdefault(a.payment_id, []).append({
            'id': a.id,
            'charge_id': a.charge_id,
            'amount': float(a.amount),
        })
    student_credit = 0.0
    if not target_period:
        for p in payments:
            student_credit += round(float(p.amount or 0) - float(allocated_by_payment.get(p.id, 0.0)), 2)
    
    # NUEVO: Pasar charge_adjustments a _build_charge_financials
    financials = _build_charge_financials(charges, allocated_map, student_credit=student_credit, today_value=today, charge_adjustments=charge_adjustments)

    charges_out = []
    for c in charges:
        meta = financials['by_charge_id'].get(c.id, {})

        charges_out.append({
            'id': c.id,
            'period': c.period,
            'due_date': c.due_date.isoformat() if c.due_date else None,
            'base_amount': float(c.base_amount or 0),
            'discount_amount': float(c.discount_amount or 0),
            'proration_mode': c.proration_mode,
            'proration_percent': float(c.proration_percent or 0),
            'proration_start_date': c.proration_start_date.isoformat() if c.proration_start_date else None,
            # Mostrar siempre el valor oficial de la cuota almacenada en fee_charges
            # (la tarifa mensual normalizada del período).
            'final_amount': float(c.final_amount or 0),
            'paid_amount': round(float(meta.get('paid', 0.0)), 2),
            'applied_credit': round(float(meta.get('applied_credit', 0.0)), 2),
            'balance': round(float(meta.get('balance', 0.0)), 2),
            'outstanding_balance': round(float(meta.get('outstanding_balance', 0.0)), 2),
            'credit_amount': round(float(meta.get('credit_amount', 0.0)), 2),
            'status': meta.get('status', 'pending'),
            'overdue': bool(meta.get('overdue')),
        })

    payments_out = []
    for p in payments:
        # Calcular períodos alcanzados por este pago
        payment_allocations = alloc_by_payment.get(p.id, [])
        periods_set = set()
        for alloc in payment_allocations:
            charge = next((c for c in charges if c.id == alloc['charge_id']), None)
            if charge and charge.period:
                periods_set.add(charge.period)
        periods_list = sorted(list(periods_set))
        periods_str = ', '.join(periods_list) if periods_list else '-'
        
        # Calcular subtotal, descuento y recargo
        subtotal = float(p.amount or 0)
        discount_amt = 0
        surcharge_amt = 0
        
        discount_type = getattr(p, 'discount_type', None)
        discount_value = float(getattr(p, 'discount_value', 0) or 0)
        if discount_type == 'percent' and discount_value > 0:
            # Subtotal original antes del descuento
            subtotal = subtotal / (1 - discount_value / 100)
            discount_amt = subtotal * (discount_value / 100)
        elif discount_type == 'fixed' and discount_value > 0:
            subtotal = subtotal + discount_value
            discount_amt = discount_value
        
        surcharge_type = getattr(p, 'surcharge_type', None)
        surcharge_value = float(getattr(p, 'surcharge_value', 0) or 0)
        if surcharge_type == 'percent' and surcharge_value > 0:
            base_for_surcharge = subtotal - discount_amt
            surcharge_amt = base_for_surcharge * (surcharge_value / 100)
        elif surcharge_type == 'fixed' and surcharge_value > 0:
            surcharge_amt = surcharge_value
        
        payments_out.append({
            'id': p.id,
            'payment_date': p.payment_date,
            'amount': float(p.amount),
            'subtotal': round(subtotal, 2),
            'discount_amount': round(discount_amt, 2),
            'surcharge_amount': round(surcharge_amt, 2),
            'periods': periods_str,
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

    last_payment = payments[0].payment_date if payments else None

    if not charges_out or financials['positive_charges_count'] == 0:
        status = 'sin_registro'
    elif financials['has_partial']:
        status = 'parcial'
    elif financials['overdue_total'] > 0:
        status = 'vencida'
    elif financials['balance_total'] > 0:
        status = 'pendiente'
    else:
        status = 'al_dia'

    return {
        'student_id': student_id,
        'status': status,
        'overdue_total': round(financials['overdue_total'], 2),
        'balance_total': round(financials['balance_total'], 2),
        'credit_total': round(financials['credit_total'], 2),
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
            'fixed_fee_enabled': (settings.discount_type or '').strip().lower() == 'fixed',
            'fixed_fee_amount': float(settings.discount_value or 0) if (settings.discount_type or '').strip().lower() == 'fixed' else 0,
            'effective_monthly_amount': round(float(cfg.monthly_amount or 0) - _compute_discount_amount(float(cfg.monthly_amount or 0), settings), 2),
        },
        'charges': charges_out,
        'payments': payments_out,
        'history': history_out,
    }


@app.route('/api/fees/config', methods=['GET', 'PUT'])
def api_fees_config():
    cfg = _get_fee_config()
    if not cfg:
        cfg = FeeConfig(monthly_amount=0, due_day=10, proration_mode='percent', proration_percent_default=100)
        db.session.add(cfg)
        db.session.commit()

    if request.method == 'GET':
        # Obtener valor mensual específico si se proporciona period
        period = request.args.get('period', '').strip()
        monthly_amount = float(cfg.monthly_amount or 0)
        
        if period:
            monthly_value = db.session.get(FeeMonthlyValue, period)
            if monthly_value:
                monthly_amount = float(monthly_value.monthly_amount or 0)
        
        return jsonify({
            'monthly_amount': monthly_amount,
            'due_day': int(cfg.due_day or 10),
            'proration_mode': cfg.proration_mode or 'percent',
            'proration_percent_default': float(cfg.proration_percent_default or 100),
        })

    # PUT: guardar valor mensual para período específico
    data = request.json or {}
    period = data.get('period', '').strip()
    
    if period and 'monthly_amount' in data:
        try:
            amount = float(data.get('monthly_amount') or 0)
        except (TypeError, ValueError):
            amount = 0
        
        monthly_value = db.session.get(FeeMonthlyValue, period)
        if monthly_value:
            monthly_value.monthly_amount = amount
            monthly_value.updated_at = datetime.utcnow()
        else:
            monthly_value = FeeMonthlyValue(period=period, monthly_amount=amount)
            db.session.add(monthly_value)
        
        db.session.commit()
        
        # CORRECCIÓN CRÍTICA: Actualizar cuotas pendientes del período con la nueva tarifa
        _update_period_charges_with_new_rate(period, amount)
        
    elif 'monthly_amount' in data:
        # Actualizar valor global si no se especifica período
        try:
            cfg.monthly_amount = float(data.get('monthly_amount') or 0)
        except (TypeError, ValueError):
            cfg.monthly_amount = 0
        db.session.commit()

    return jsonify({'status': 'ok'})


@app.route('/api/fees/student/<int:student_id>', methods=['GET'])
def api_fees_student(student_id: int):
    student = db.session.get(Student, student_id)
    if not student:
        return jsonify({'error': 'Alumno no encontrado'}), 404
    
    # CORRECCIÓN CRÍTICA: Recibir período seleccionado desde el frontend
    target_period = request.args.get('period', '').strip()
    if not target_period:
        # Si no se especifica período, usar el mes actual
        today = date.today()
        target_period = f'{today.year:04d}-{today.month:02d}'
    
    data = _serialize_student_fees(student_id, target_period=target_period)
    
    # Agregar el estado del alumno para el período específico
    is_active_in_period = _get_student_status_for_period(student_id, target_period)
    
    data['student'] = {
        'id': student.id,
        'full_name': student.full_name,
        'last_name': student.last_name,
        'first_name': student.first_name,
        'status': student.status,
        'belt': student.belt,
        'is_active_in_period': is_active_in_period,
        'target_period': target_period,
    }
    return jsonify(data)


@app.route('/api/fees/student/<int:student_id>/settings', methods=['PUT'])
def api_fees_student_settings(student_id: int):
    student = db.session.get(Student, student_id)
    if not student:
        return jsonify({'error': 'Alumno no encontrado'}), 404

    settings = _get_student_fee_settings(student_id)
    cfg = _get_fee_config()
    data = request.json or {}
    fixed_fee_enabled = bool(data.get('fixed_fee_enabled'))
    if fixed_fee_enabled:
        settings.discount_type = 'fixed'
        try:
            fixed_amount = float(data.get('fixed_fee_amount') or 0)
        except Exception:
            fixed_amount = 0
        if fixed_amount < 0:
            fixed_amount = 0
        settings.discount_value = fixed_amount
        _refresh_student_fee_charges(student_id, cfg, settings)
        db.session.commit()
        return jsonify({'status': 'ok'})

    dtype = data.get('discount_type')
    if dtype is None or dtype == '':
        settings.discount_type = None
    else:
        dtype_norm = str(dtype).strip().lower()
        if dtype_norm in ('percent', 'amount', 'fixed'):
            settings.discount_type = dtype_norm

    if 'discount_value' in data:
        try:
            settings.discount_value = float(data.get('discount_value') or 0)
        except Exception:
            settings.discount_value = 0

    _refresh_student_fee_charges(student_id, cfg, settings)
    db.session.commit()
    return jsonify({'status': 'ok'})


@app.route('/api/fees/student/<int:student_id>/charges/generate', methods=['POST'])
def api_fees_generate_charge(student_id: int):
    student = db.session.get(Student, student_id)
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
    charge = db.session.get(FeeCharge, charge_id)
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
    period_filter = _parse_period(request.args.get('period'))
    current_period = f'{today.year:04d}-{today.month:02d}'

    students = Student.query.order_by(
        (Student.last_name.is_(None)).asc(),
        Student.last_name.asc(),
        Student.first_name.asc(),
    ).all()

    # CORRECCIÓN: Si hay filtro de período, usar estado histórico para ese período
    # Si no hay filtro, usar el estado actual del alumno
    active_students = []
    active_ids = []
    for s in students:
        # En cuotas se deben mostrar SIEMPRE todos los alumnos.
        # El estado Activo/Inactivo es mensual y solo afecta el badge/estado, no la visibilidad.
        active_students.append(s)
        active_ids.append(s.id)

    charges = []
    if active_ids:
        charges = FeeCharge.query.filter(FeeCharge.student_id.in_(active_ids)).all()
    if period_filter:
        charges = [c for c in charges if c.period == period_filter['period']]

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

    payments = []
    if active_ids:
        payments = FeePayment.query.filter(FeePayment.student_id.in_(active_ids)).all()
    payment_ids = [p.id for p in payments]
    payment_allocations = []
    if payment_ids:
        payment_allocations = FeeAllocation.query.filter(FeeAllocation.payment_id.in_(payment_ids)).all()
    allocated_by_payment = {}
    for a in payment_allocations:
        allocated_by_payment[a.payment_id] = allocated_by_payment.get(a.payment_id, 0.0) + float(a.amount)
    student_credit_map = {}
    for p in payments:
        student_credit_map[p.student_id] = student_credit_map.get(p.student_id, 0.0) + round(float(p.amount or 0) - float(allocated_by_payment.get(p.id, 0.0)), 2)

    period_payment_total_map = {}
    if period_filter:
        selected_period = period_filter['period']
        for p in payments:
            payment_period = str(p.payment_date or '')[:7]
            if payment_period != selected_period:
                continue
            period_payment_total_map[p.student_id] = period_payment_total_map.get(p.student_id, 0.0) + float(p.amount or 0)

    out = []
    for s in active_students:
        if period_filter:
            is_active_in_period = _get_student_status_for_period(s.id, period_filter['period'])
        else:
            is_active_in_period = _get_student_status_for_period(s.id, current_period)

        st_charges = charges_by_student.get(s.id, [])

        if period_filter:
            st_charge_adjustments = {}
            student_credit_for_calc = 0.0
        else:
            st_charge_ids = [c.id for c in st_charges]
            st_charge_adjustments = _get_charge_adjustments_from_payments(st_charge_ids, s.id)
            student_credit_for_calc = student_credit_map.get(s.id, 0.0)

        financials = _build_charge_financials(
            st_charges,
            paid_by_charge,
            student_credit=student_credit_for_calc,
            today_value=today,
            charge_adjustments=st_charge_adjustments,
        )
        period_charge_total = 0.0
        if period_filter:
            for c in st_charges:
                period_charge_total += float(c.final_amount or 0)
        period_generated_credit = 0.0
        if period_filter:
            period_generated_credit = round(max(period_payment_total_map.get(s.id, 0.0) - period_charge_total, 0.0), 2)

        # Cálculo de estado para el mes seleccionado (solo alumnos activos)
        if period_filter:
            selected_period = period_filter['period']
            period_charge = next((c for c in st_charges if c.period == selected_period), None)

            if not is_active_in_period:
                status = 'inactivo'
            elif period_charge:
                charge_meta = financials['by_charge_id'].get(period_charge.id, {})
                outstanding = float(charge_meta.get('outstanding_balance', 0.0))
                paid_amount = float(charge_meta.get('paid', 0.0))
                
                if outstanding <= 0:
                    status = 'al_dia'
                elif paid_amount > 0:
                    status = 'parcial'
                else:
                    # Regla de negocio: día 1-10 = pendiente, después del día 10 = vencida
                    year = period_filter['year']
                    month = period_filter['month']
                    cutoff_date = date(year, month, 10)
                    
                    if today > cutoff_date:
                        status = 'vencida'
                    else:
                        status = 'pendiente'
            else:
                # Alumno activo sin cuota del mes → verificar si ya pasó el día 10
                year = period_filter['year']
                month = period_filter['month']
                cutoff_date = date(year, month, 10)
                
                if today > cutoff_date:
                    status = 'vencida'
                else:
                    status = 'pendiente'
        else:
            # Lógica general (sin filtro de período)
            if not is_active_in_period:
                status = 'inactivo'
            elif not st_charges or financials['positive_charges_count'] == 0:
                status = 'pendiente'  # Activo sin cuotas → pendiente
            elif financials['has_partial']:
                status = 'parcial'
            elif financials['overdue_total'] > 0:
                status = 'vencida'
            elif financials['balance_total'] > 0:
                status = 'pendiente'
            else:
                status = 'al_dia'
        
        # Calcular deuda pendiente con meses adeudados
        pending_charges = [c for c in st_charges if financials['by_charge_id'].get(c.id, {}).get('outstanding_balance', 0) > 0]
        pending_periods = sorted(set(c.period for c in pending_charges))
        debt_detail = ''
        if pending_periods:
            # Formatear los períodos en formato legible
            month_names = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
            formatted_periods = []
            for p in pending_periods:
                try:
                    year, month = p.split('-')
                    month_idx = int(month) - 1
                    if 0 <= month_idx < 12:
                        formatted_periods.append(f"{month_names[month_idx]} {year}")
                except:
                    formatted_periods.append(p)
            debt_detail = ' y '.join(formatted_periods) if len(formatted_periods) <= 2 else f"{len(formatted_periods)} meses"

        out.append({
            'student_id': s.id,
            'full_name': s.full_name,
            'last_name': s.last_name,
            'first_name': s.first_name,
            'belt': s.belt,
            'status': status,
            'is_active': is_active_in_period,
            'overdue_total': round(financials['overdue_total'], 2),
            'balance_total': round(financials['balance_total'], 2),
            'debt_detail': debt_detail,
            'credit_total': round(financials['credit_total'], 2),
            'period_generated_credit': round(period_generated_credit, 2),
            'last_payment': last_payment_map.get(s.id),
        })

    return jsonify(out)


@app.route('/api/fees/history-integral', methods=['GET'])
def api_fees_history_integral():
    """
    Endpoint para historial integral de cobros con KPIs de gestión.
    Retorna pagos reales registrados, no cuotas pendientes.
    """
    _ensure_fees_tables()
    period_filter = _parse_period(request.args.get('period'))
    today = date.today()
    
    # Obtener todos los alumnos para cálculos
    all_students = Student.query.all()
    active_students = [s for s in all_students if getattr(s, 'is_active', True)]
    active_count = len(active_students)
    
    # Obtener pagos filtrados por período si aplica
    payments_query = FeePayment.query.order_by(FeePayment.payment_date.desc(), FeePayment.id.desc())
    payments = payments_query.all()
    
    if period_filter:
        selected_period = period_filter['period']
        payments = [p for p in payments if str(p.payment_date or '')[:7] == selected_period]
    
    # Obtener información de alumnos
    student_ids = list(set(p.student_id for p in payments))
    students_map = {}
    if student_ids:
        students = Student.query.filter(Student.id.in_(student_ids)).all()
        students_map = {s.id: s for s in students}
    
    # Obtener asignaciones para períodos
    payment_ids = [p.id for p in payments]
    allocations = []
    if payment_ids:
        allocations = FeeAllocation.query.filter(FeeAllocation.payment_id.in_(payment_ids)).all()
    
    # Mapear allocations por payment_id
    allocations_by_payment = {}
    charge_ids = set()
    for a in allocations:
        allocations_by_payment.setdefault(a.payment_id, []).append(a)
        charge_ids.add(a.charge_id)
    
    # Obtener charges para períodos
    charges_map = {}
    if charge_ids:
        charges = FeeCharge.query.filter(FeeCharge.id.in_(charge_ids)).all()
        charges_map = {c.id: c for c in charges}
    
    # Construir lista de pagos con info completa
    payments_data = []
    total_amount = 0
    unique_students = set()
    
    for p in payments:
        student = students_map.get(p.student_id)
        if not student:
            continue
        
        # Obtener períodos abonados
        payment_allocations = allocations_by_payment.get(p.id, [])
        periods_list = []
        for alloc in payment_allocations:
            charge = charges_map.get(alloc.charge_id)
            if charge and charge.period:
                periods_list.append(charge.period)
        
        periods_str = ', '.join(sorted(set(periods_list))) if periods_list else '-'
        
        # Reconstruir subtotal y montos desde campos reales
        # amount es el total final pagado
        # Necesitamos trabajar hacia atrás para obtener subtotal
        amount = float(p.amount or 0)
        discount_value = float(p.discount_value or 0)
        surcharge_value = float(p.surcharge_value or 0)
        
        # Calcular subtotal y montos reales de descuento/recargo
        if p.discount_type == 'percent':
            # amount = subtotal * (1 - discount_value/100) + surcharge
            # Necesitamos resolver para subtotal
            if p.surcharge_type == 'percent':
                # Muy complejo, usamos amount como base
                subtotal = amount
                discount_amt = 0
                surcharge_amt = 0
            elif p.surcharge_type == 'fixed':
                subtotal_after_discount = amount - surcharge_value
                subtotal = subtotal_after_discount / (1 - discount_value / 100) if discount_value < 100 else 0
                discount_amt = subtotal * (discount_value / 100)
                surcharge_amt = surcharge_value
            else:
                subtotal = amount / (1 - discount_value / 100) if discount_value < 100 else 0
                discount_amt = subtotal * (discount_value / 100)
                surcharge_amt = 0
        elif p.discount_type == 'fixed':
            if p.surcharge_type == 'percent':
                # (subtotal - discount) * (1 + surcharge/100) = amount
                subtotal_after_discount = amount / (1 + surcharge_value / 100) if surcharge_value > -100 else 0
                subtotal = subtotal_after_discount + discount_value
                discount_amt = discount_value
                surcharge_amt = subtotal_after_discount * (surcharge_value / 100)
            elif p.surcharge_type == 'fixed':
                subtotal = amount + discount_value - surcharge_value
                discount_amt = discount_value
                surcharge_amt = surcharge_value
            else:
                subtotal = amount + discount_value
                discount_amt = discount_value
                surcharge_amt = 0
        else:
            # Sin descuento
            if p.surcharge_type == 'percent':
                subtotal = amount / (1 + surcharge_value / 100) if surcharge_value > -100 else 0
                discount_amt = 0
                surcharge_amt = subtotal * (surcharge_value / 100)
            elif p.surcharge_type == 'fixed':
                subtotal = amount - surcharge_value
                discount_amt = 0
                surcharge_amt = surcharge_value
            else:
                subtotal = amount
                discount_amt = 0
                surcharge_amt = 0
        
        total_amount += amount
        unique_students.add(p.student_id)
        
        payments_data.append({
            'id': p.id,
            'payment_date': str(p.payment_date) if p.payment_date else '',
            'student_id': p.student_id,
            'student_name': student.full_name or f"{student.last_name or ''} {student.first_name or ''}",
            'periods': periods_str,
            'subtotal': round(subtotal, 2),
            'discount_amount': round(discount_amt, 2),
            'surcharge_amount': round(surcharge_amt, 2),
            'amount': round(amount, 2),
            'notes': p.notes or '',
        })
    
    # Calcular KPIs simplificados
    # KPI: Alumnos al día y pendientes en el período seleccionado
    students_up_to_date = 0
    students_pending = 0
    
    if period_filter and active_students:
        selected_period = period_filter['period']
        for s in active_students:
            # Verificar si tiene cuota del período y está pagada
            charges = FeeCharge.query.filter_by(student_id=s.id, period=selected_period).all()
            if not charges:
                # No tiene cuota generada para este mes, cuenta como pendiente
                students_pending += 1
                continue
            
            # Calcular si está al día
            charge_ids_student = [c.id for c in charges]
            allocations_student = FeeAllocation.query.filter(FeeAllocation.charge_id.in_(charge_ids_student)).all()
            paid_by_charge = {}
            for a in allocations_student:
                paid_by_charge[a.charge_id] = paid_by_charge.get(a.charge_id, 0.0) + float(a.amount)
            
            all_paid = True
            for c in charges:
                balance = float(c.final_amount or 0) - paid_by_charge.get(c.id, 0.0)
                if balance > 0.01:
                    all_paid = False
                    break
            
            if all_paid:
                students_up_to_date += 1
            else:
                students_pending += 1
    
    # KPI: Tasa de cobro (alumnos al día / alumnos activos)
    collection_rate = round((students_up_to_date / active_count * 100), 1) if active_count > 0 else 0
    
    kpis = {
        'total_amount': round(total_amount, 2),
        'students_up_to_date': students_up_to_date,
        'students_pending': students_pending,
        'collection_rate': collection_rate,
    }
    
    return jsonify({
        'payments': payments_data,
        'kpis': kpis,
    })


@app.route('/api/fees/student/<int:student_id>/payments', methods=['POST'])
def api_fees_register_payment(student_id: int):
    student = db.session.get(Student, student_id)
    if not student:
        return jsonify({'error': 'Alumno no encontrado'}), 404

    body = request.json or {}
    payment_date = body.get('payment_date') or datetime.now().strftime('%Y-%m-%d')
    amount_raw = body.get('amount', 0)
    try:
        amount = float(amount_raw or 0)
    except Exception:
        amount = 0
    if amount <= 0:
        return jsonify({'error': 'El monto abonado debe ser mayor a 0.'}), 400

    discount_type = body.get('discount_type')
    if discount_type not in ('percent', 'fixed'):
        discount_type = None
    
    discount_value = 0
    if discount_type:
        try:
            discount_value = float(body.get('discount_value', 0) or 0)
        except Exception:
            discount_value = 0
        if discount_value < 0:
            discount_value = 0
    
    surcharge_type = body.get('surcharge_type')
    if surcharge_type not in ('percent', 'fixed'):
        surcharge_type = None
    
    surcharge_value = 0
    if surcharge_type:
        try:
            surcharge_value = float(body.get('surcharge_value', 0) or 0)
        except Exception:
            surcharge_value = 0
        if surcharge_value < 0:
            surcharge_value = 0

    method = body.get('method') or 'cash'
    if method not in ('cash', 'transfer'):
        method = 'cash'
    reference = body.get('reference')
    notes = body.get('notes')

    payment = FeePayment(
        student_id=student_id,
        payment_date=payment_date,
        amount=round(amount, 2),
        discount_type=discount_type,
        discount_value=round(discount_value, 2) if discount_type else 0,
        surcharge_type=surcharge_type,
        surcharge_value=round(surcharge_value, 2) if surcharge_type else 0,
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

    if not charges:
        db.session.rollback()
        return jsonify({'error': 'No hay cuotas seleccionadas para aplicar el pago.'}), 400

    allocated_map = _get_charge_allocated_amounts([c.id for c in charges])
    total_pending_selected = 0.0
    for c in charges:
        total = float(c.final_amount or 0)
        already = float(allocated_map.get(c.id, 0.0))
        remaining_charge = round(total - already, 2)
        if remaining_charge > 0:
            total_pending_selected += remaining_charge

    total_pending_selected = round(total_pending_selected, 2)
    if total_pending_selected <= 0:
        db.session.rollback()
        return jsonify({'error': 'Las cuotas seleccionadas ya están saldadas.'}), 400

    if round(amount, 2) > total_pending_selected:
        db.session.rollback()
        return jsonify({'error': f'El monto abonado (${round(amount, 2):.2f}) supera el saldo pendiente seleccionado (${total_pending_selected:.2f}).'}), 400

    remaining_payment = round(amount, 2)
    allocated_any = False

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
        allocated_any = True
        remaining_payment = round(remaining_payment - applied, 2)

    if not allocated_any:
        db.session.rollback()
        return jsonify({'error': 'No se pudo aplicar el pago a cuotas pendientes.'}), 400

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
    payment = db.session.get(FeePayment, payment_id)
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
    event = db.session.get(Event, event_id)
    if not event or event.type != 'exam':
        return jsonify({'error': 'Examen no encontrado'}), 404

    # (Opcional) en el futuro se podría vincular Student vía BD.
    student = None
    data = request.json or {}
    student_id = data.get('student_id')
    if student_id is not None:
        student = db.session.get(Student, student_id)

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

    event = db.session.get(Event, event_id)
    if not event or event.type != 'exam':
        return jsonify({'error': 'Examen no encontrado'}), 404

    data = request.json or {}
    student_id = data.get('student_id')
    student = db.session.get(Student, student_id) if student_id is not None else None

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

    event = db.session.get(Event, event_id)
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
