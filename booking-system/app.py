from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS  # 記得要裝 flask-cors 才能讓前端順利呼叫

app = Flask(__name__)
CORS(app)  # 允許跨域請求

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///volleyball.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# 資料庫模型設計區
# ==========================================

participants_table = db.Table('participants',
                              db.Column('user_id', db.String(20), db.ForeignKey('user.student_id'), primary_key=True),
                              db.Column('reservation_id', db.Integer, db.ForeignKey('reservation.id'), primary_key=True)
                              )


class User(db.Model):
    student_id = db.Column(db.String(20), primary_key=True)
    password = db.Column(db.String(128), nullable=False)


class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    court_name = db.Column(db.String(10), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    hour = db.Column(db.Integer, nullable=False)
    host_id = db.Column(db.String(20), db.ForeignKey('user.student_id'), nullable=False)

    participants = db.relationship('User', secondary=participants_table, lazy='subquery',
                                   backref=db.backref('joined_groups', lazy=True))


# ==========================================
# API 路由區 (Endpoints)
# ==========================================

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    student_id = data.get('student_id')
    password = data.get('password')

    if User.query.filter_by(student_id=student_id).first():
        return jsonify({'message': '此學號已註冊過囉'}), 400

    hashed_password = generate_password_hash(password)
    new_user = User(student_id=student_id, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': '註冊成功！'}), 201


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(student_id=data.get('student_id')).first()

    if user and check_password_hash(user.password, data.get('password')):
        return jsonify({'message': '登入成功！', 'student_id': user.student_id}), 200
    return jsonify({'message': '學號或密碼錯誤'}), 401


# 1. 更新：取得所有預約 (給日曆顯示用)
@app.route('/api/reservations', methods=['GET'])
def get_reservations():
    reservations = Reservation.query.all()
    result = []
    for r in reservations:
        # 抓出這個揪團裡所有人的學號，回傳給前端
        participant_ids = [p.student_id for p in r.participants]
        result.append({
            'id': r.id,
            'court_name': r.court_name,
            'date': r.date,
            'hour': r.hour,
            'host_id': r.host_id,
            'participants_count': len(r.participants),
            'participants': participant_ids  # 新增這個欄位
        })
    return jsonify(result), 200


# 2. 新增：退出揪團 / 取消預約 API
@app.route('/api/reservations/<int:res_id>/leave', methods=['POST'])
def leave_reservation(res_id):
    data = request.get_json()
    student_id = data.get('student_id')
    user = User.query.filter_by(student_id=student_id).first()
    reservation = db.session.get(Reservation, res_id)

    if not reservation or not user:
        return jsonify({'message': '資料錯誤'}), 404

    if user in reservation.participants:
        reservation.participants.remove(user)  # 將使用者從揪團名單移除

        # 如果退出後這個揪團人數變成 0，就直接刪除這個預約，釋放場地！
        if len(reservation.participants) == 0:
            db.session.delete(reservation)

        db.session.commit()
        return jsonify({'message': '已成功退出揪團 / 取消預約！'}), 200
    else:
        return jsonify({'message': '你不在這個揪團中喔！'}), 400

# 新增預約
@app.route('/api/reservations', methods=['POST'])
def create_reservation():
    data = request.get_json()
    student_id = data.get('student_id')

    user = User.query.filter_by(student_id=student_id).first()
    if not user:
        return jsonify({'message': '找不到使用者'}), 404

    # 檢查該時段場地是否被借走
    conflict = Reservation.query.filter_by(court_name=data.get('court_name'), date=data.get('date'),
                                           hour=data.get('hour')).first()
    if conflict:
        return jsonify({'message': '該時段已被預約'}), 400

    new_res = Reservation(
        court_name=data.get('court_name'),
        date=data.get('date'),
        hour=data.get('hour'),
        host_id=student_id
    )
    new_res.participants.append(user)  # 發起人自動加入
    db.session.add(new_res)
    db.session.commit()
    return jsonify({'message': '預約成功！'}), 201


# 加入別人的揪團
@app.route('/api/reservations/<int:res_id>/join', methods=['POST'])
def join_reservation(res_id):
    data = request.get_json()
    user = User.query.filter_by(student_id=data.get('student_id')).first()
    reservation = db.session.get(Reservation, res_id)

    if not reservation or not user:
        return jsonify({'message': '資料錯誤'}), 404

    if user in reservation.participants:
        return jsonify({'message': '你已經在這個揪團裡了'}), 400

    if len(reservation.participants) >= 14:
        return jsonify({'message': '揪團人數已達 14 人上限！'}), 400

    reservation.participants.append(user)
    db.session.commit()
    return jsonify({'message': '成功加入揪團！'}), 200


# ==========================================
# 啟動與初始化區
# ==========================================
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)