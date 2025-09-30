class Schedule_bd:
    def __init__(self, db_name='schedule.db'):
        self.db_name = db_name
        self.init_db()
        
    def init_db(self):
        con = sqlite3.connect(self.db_name)
        cursor = con.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedule(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT BOT NULL,
                time_slot TEXT NOT NULL,
                is_available BOOLEAN DEFAULT TRUE,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                date TEXT,
                time_slot TEXT,
                booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        con.commit()
        con.close()
        
        def generate_schedule(self):
            con = sqlite3.connect(self.db_name)
            cursor = con.cursor()
            cursor.execute("DELETE FROM schedule")
            
            today = datetime.now()
            day_before_sunday = (6 - today.weekday()) % 7
            start_day = today + timedelta(days=day_before_sunday)
            
            time_slots = [
                ((8, 0), (8, 35)), ((8, 35), (9, 10)), ((9, 10), (9, 45)), 
                ((9, 45), (10, 20)), ((10, 20), (10, 55)), ((10, 55), (11, 30)), 
                ((11, 30), (12, 5)), ((12, 5), (12, 40)), ((12, 40), (13, 15)), 
                ((13, 15), (13, 50)), ((13, 50), (14, 25)), ((14, 25), (15, 0)), 
                ((15, 0), (15, 35)), ((15, 35), (16, 10)), ((16, 10), (16, 45)), 
                ((16, 45), (17, 20)), ((17, 20), (17, 55)), ((17, 55), (18, 30)), 
                ((18, 30), (19, 5)), ((19, 5), (19, 40))
            ]
            
            schedule_date = []
            for day in range(7):
                current_date = start_day + timedelta(days=day)
                date_str = current_date.strftime('%Y-%m-%d')

                for time_slot in time_slots:
                    schedule_date.append((date_str, time_slot, True, None, None))
                    
            cursor.executemany('''
                INSERT INTO schedule (date, time_slot, is_available, user_id, username)
                VALUES (?, ?, ?, ?, ?)
            ''', schedule_date)
            
            con.commit()
            con.close()