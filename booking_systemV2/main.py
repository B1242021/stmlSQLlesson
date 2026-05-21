from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash

app = FastAPI()

# 允許前端跨域呼叫 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 資料庫設定區 (請修改為你的密碼)
# ==========================================
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "volleyball",
    "user": "postgres",
    "password": "1234"  # <--- 記得改這裡
}


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


# ==========================================
# 定義接收資料的格式 (Pydantic Models)
# ==========================================
class UserAuth(BaseModel):
    student_id: str
    password: str


class ReservationCreate(BaseModel):
    student_id: str
    court_name: str
    date: str
    hour: int


class JoinLeaveAction(BaseModel):
    student_id: str


# ==========================================
# API 路由區 (Endpoints)
# ==========================================

@app.post("/api/register")
def register(user: UserAuth):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 檢查是否註冊過
        cursor.execute("SELECT * FROM users WHERE student_id = %s", (user.student_id,))
        if cursor.fetchone():
            return {"message": "此學號已註冊過囉"}

        # 加密密碼並新增
        hashed_pw = generate_password_hash(user.password)
        cursor.execute("INSERT INTO users (student_id, password) VALUES (%s, %s)", (user.student_id, hashed_pw))
        conn.commit()
        return {"message": "註冊成功！"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cursor.close()
        conn.close()


@app.post("/api/login")
def login(user: UserAuth):
    conn = get_db_connection()
    # 使用 RealDictCursor 讓撈出來的資料變成字典格式，比較好操作
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT * FROM users WHERE student_id = %s", (user.student_id,))
        db_user = cursor.fetchone()

        if db_user and check_password_hash(db_user['password'], user.password):
            return {"message": "登入成功！", "student_id": db_user['student_id']}
        raise HTTPException(status_code=401, detail="學號或密碼錯誤")
    finally:
        cursor.close()
        conn.close()


@app.get("/api/reservations")
def get_reservations():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # 抓取所有預約
        cursor.execute("SELECT * FROM reservations")
        reservations = cursor.fetchall()

        result = []
        for r in reservations:
            # 針對每個預約，去 participants 表抓出有誰參加
            cursor.execute("SELECT user_id FROM participants WHERE reservation_id = %s", (r['id'],))
            participants = [row['user_id'] for row in cursor.fetchall()]

            result.append({
                "id": r['id'],
                "court_name": r['court_name'],
                "date": r['date'],
                "hour": r['hour'],
                "host_id": r['host_id'],
                "participants_count": len(participants),
                "participants": participants
            })
        return result
    finally:
        cursor.close()
        conn.close()


@app.post("/api/reservations")
def create_reservation(res: ReservationCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 檢查時段衝突
        cursor.execute("SELECT * FROM reservations WHERE court_name = %s AND date = %s AND hour = %s",
                       (res.court_name, res.date, res.hour))
        if cursor.fetchone():
            return {"message": "該時段已被預約"}

        # 建立預約 (RETURNING id 可以直接拿到剛剛產生的新 id)
        cursor.execute("""
            INSERT INTO reservations (court_name, date, hour, host_id) 
            VALUES (%s, %s, %s, %s) RETURNING id
        """, (res.court_name, res.date, res.hour, res.student_id))
        new_id = cursor.fetchone()[0]

        # 把發起人加入參與者名單
        cursor.execute("INSERT INTO participants (user_id, reservation_id) VALUES (%s, %s)",
                       (res.student_id, new_id))
        conn.commit()
        return {"message": "預約成功！"}
    finally:
        cursor.close()
        conn.close()


@app.post("/api/reservations/{res_id}/join")
def join_reservation(res_id: int, action: JoinLeaveAction):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 檢查目前人數
        cursor.execute("SELECT COUNT(*) FROM participants WHERE reservation_id = %s", (res_id,))
        count = cursor.fetchone()[0]
        if count >= 14:
            return {"message": "揪團人數已達 14 人上限！"}

        cursor.execute("INSERT INTO participants (user_id, reservation_id) VALUES (%s, %s)",
                       (action.student_id, res_id))
        conn.commit()
        return {"message": "成功加入揪團！"}
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return {"message": "你已經在這個揪團裡了"}
    finally:
        cursor.close()
        conn.close()


@app.post("/api/reservations/{res_id}/leave")
def leave_reservation(res_id: int, action: JoinLeaveAction):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 移除參與者
        cursor.execute("DELETE FROM participants WHERE user_id = %s AND reservation_id = %s",
                       (action.student_id, res_id))

        # 檢查剩餘人數，如果變 0 就刪除該預約
        cursor.execute("SELECT COUNT(*) FROM participants WHERE reservation_id = %s", (res_id,))
        if cursor.fetchone()[0] == 0:
            cursor.execute("DELETE FROM reservations WHERE id = %s", (res_id,))

        conn.commit()
        return {"message": "已成功退出揪團 / 取消預約！"}
    finally:
        cursor.close()
        conn.close()