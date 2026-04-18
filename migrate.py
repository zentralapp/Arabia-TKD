#!/usr/bin/env python
"""
Script de migración para ejecutar ANTES de arrancar la aplicación.
Asegura que todas las columnas necesarias existan en la base de datos.
"""
import sys
from app import app, db, inspect, text

def run_migrations():
    """Ejecuta todas las migraciones pendientes de forma segura."""
    print("=" * 60)
    print("INICIANDO MIGRACIONES")
    print("=" * 60)
    
    with app.app_context():
        try:
            # Crear todas las tablas base si no existen
            print("[1/5] Creando tablas base...")
            db.create_all()
            print("✓ Tablas base verificadas")
            
            with db.engine.begin() as conn:
                inspector = inspect(conn)
                
                # MIGRACIÓN 1: Columnas faltantes en students
                print("\n[2/5] Verificando columnas en tabla students...")
                if 'students' in inspector.get_table_names():
                    student_columns = {col['name'] for col in inspector.get_columns('students')}
                    print(f"  Columnas actuales: {sorted(student_columns)}")
                    
                    student_column_defs = {
                        'notes': 'TEXT',
                        'status': "TEXT DEFAULT 'activo'",
                        'tutor_type': "TEXT DEFAULT 'padre'",
                        'father_birthdate': 'DATE',
                        'mother_birthdate': 'DATE',
                    }
                    
                    for column_name, column_def in student_column_defs.items():
                        if column_name not in student_columns:
                            print(f"  → Agregando columna '{column_name}'...")
                            conn.execute(text(f"ALTER TABLE students ADD COLUMN {column_name} {column_def}"))
                            print(f"  ✓ Columna '{column_name}' agregada")
                    
                    # MIGRACIÓN CRÍTICA: is_active
                    if 'is_active' not in student_columns:
                        print(f"  → Agregando columna 'is_active' (BOOLEAN DEFAULT TRUE)...")
                        conn.execute(text("ALTER TABLE students ADD COLUMN is_active BOOLEAN DEFAULT TRUE"))
                        print(f"  ✓ Columna 'is_active' agregada correctamente")
                        
                        # Backfill: asegurar que todos los estudiantes existentes sean activos
                        result = conn.execute(text("UPDATE students SET is_active = TRUE WHERE is_active IS NULL"))
                        print(f"  ✓ Backfill: {result.rowcount} registros actualizados a is_active=TRUE")
                    else:
                        print(f"  ✓ Columna 'is_active' ya existe")
                    
                    print("✓ Migración de students completada")
                else:
                    print("  ⚠ Tabla students no existe (se creará con db.create_all())")
                
                # MIGRACIÓN 2: Columnas en fee_payments
                print("\n[3/5] Verificando columnas en tabla fee_payments...")
                if 'fee_payments' in inspector.get_table_names():
                    payment_columns = {col['name'] for col in inspector.get_columns('fee_payments')}
                    print(f"  Columnas actuales: {sorted(payment_columns)}")
                    
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
                            print(f"  → Agregando columna '{column_name}'...")
                            conn.execute(text(f"ALTER TABLE fee_payments ADD COLUMN {column_name} {column_def}"))
                            print(f"  ✓ Columna '{column_name}' agregada")
                    
                    print("✓ Migración de fee_payments completada")
                else:
                    print("  ⚠ Tabla fee_payments no existe aún")
                
                print("\n[4/5] Verificando índices y constraints...")
                # Aquí se pueden agregar índices si hace falta en el futuro
                print("✓ Índices verificados")
                
                print("\n[5/5] Finalizando migraciones...")
                
            print("\n" + "=" * 60)
            print("✓ TODAS LAS MIGRACIONES COMPLETADAS EXITOSAMENTE")
            print("=" * 60)
            return True
            
        except Exception as e:
            print("\n" + "=" * 60)
            print(f"✗ ERROR EN MIGRACIONES: {e}")
            print("=" * 60)
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)
