from configparser import ConfigParser
from mysql.connector import MySQLConnection, errors


class MySql:
    def __init__(self):
        self.conn = MySQLConnection(**self.read_db_config())
        self.c = self.conn.cursor(buffered=True)

    def close_and_commit(self):
        self.conn.commit()
        self.c.close()

    def read_db_config(self, filename='config.ini', section='mysql'):
        """ Read database configuration file and return a dictionary object
        :param filename: name of the configuration file
        :param section: section of database configuration
        :return: a dictionary of database parameters
        """
        # create parser and read ini configuration file
        parser = ConfigParser()
        parser.read(filename)

        # get section, default to mysql
        db = {}
        if parser.has_section(section):
            items = parser.items(section)
            for item in items:
                db[item[0]] = item[1]
        else:
            raise Exception('{0} not found in the {1} file'.format(section, filename))

        return db

    def store_user(self, user_id):
        try:
            self.c.execute("insert into users (user_id) values (%s)", (user_id,))
        except errors.IntegrityError:
            pass

    def get_marathon(self):
        self.c.execute("SELECT * FROM marathons WHERE status=1")

    def get_task(self):
        self.get_marathon()
        curr_marathon = self.c.fetchone()[0]
        self.c.execute("SELECT * FROM tasks WHERE marathon_id = (%s)", (curr_marathon,))

    def get_task_data_text(self, task_id):
        self.c.execute("SELECT * FROM task_data WHERE task_id = (%s) and sort = 'text'", (task_id,))

    def get_task_data_file(self, task_id):
        self.c.execute(
            "SELECT * FROM task_data WHERE task_id = (%s) and (sort = 'photo' or sort = 'audio' or sort = 'document')",
            (task_id,))

    def insert_task_text(self, order, text, type_msg):
        self.get_marathon()
        curr_marathon = self.c.fetchone()[0]
        self.c.execute("INSERT INTO `marathon_bot`.`tasks` (`marathon_id`,`rank`) VALUES (%s,%s)",
                       (curr_marathon, order))
        self.get_task()
        task = self.c.fetchall()[-1]
        self.insert_task(task[0], text, type_msg)

    def insert_task(self, task_id, data, type_msg):
        self.c.execute("INSERT INTO task_data (task_id, data, sort) VALUES (%s, %s, %s)", (task_id, data, type_msg))

    def update_task_text(self, text, task_id):
        self.c.execute("UPDATE task_data SET data = (%s) WHERE task_id = (%s) and sort = 'text'", (text, task_id))

    def delete_task(self, task_id):
        self.c.execute("DELETE FROM tasks WHERE task_id= (%s)", (task_id,))
        self.c.execute("DELETE FROM task_data WHERE task_id= (%s)", (task_id,))

    def count_user(self):
        self.c.execute("SELECT COUNT(*) FROM users")

    def count_banned_user(self):
        self.c.execute("SELECT COUNT(*) FROM users WHERE lively = 1")

    def get_tariffs(self):
        self.c.execute("SELECT * FROM tariffs")

    def update_tariff(self, plan, number):
        self.c.execute("UPDATE tariffs SET pay = (%s) WHERE tariff_id = (%s)", (number, plan))

    def insert_payment(self, payment_id, user_id, marathon_id, tariff, message_id):
        self.c.execute(
            "INSERT INTO payments (payment_id, user_id, marathon_id, tariff, message_id) VALUES (%s, %s, %s, %s, %s)",
            (payment_id, user_id, marathon_id, tariff, message_id))

    def get_payments(self):
        self.c.execute("SELECT * FROM payments")

    def select_users_payments(self):
        self.c.execute("SELECT DISTINCT user_id FROM payments")
        users = self.c.fetchall()
        return [i[0] for i in users]

    def select_users_task(self):
        self.c.execute("SELECT DISTINCT user_id FROM user_task")
        users = self.c.fetchall()
        return [i[0] for i in users]

    def delete_payment(self, user_id):
        self.c.execute("DELETE FROM payments WHERE user_id =(%s)", (user_id,))

    def insert_user_task(self, user_id, marathon_id, task_id, tariff, message_id):
        self.c.execute(
            "INSERT INTO user_task (user_id, marathon_id, task_id, tariff, message_id) VALUES (%s, %s, %s, %s, %s)",
            (user_id, marathon_id, task_id, tariff, message_id))

    def select_message_id_task(self, user_id):
        self.c.execute("SELECT message_id FROM user_task WHERE user_id = (%s)", (user_id,))

    def delete_user_task(self, user_id=None):
        if user_id:
            self.c.execute("DELETE FROM user_task WHERE user_id = (%s)", (user_id,))
        else:
            self.c.execute("DELETE FROM user_task")

    def reset_marathon(self):
        for table in ["payments", "user_task", "user_marathon", "tasks", "task_data", "marathons"]:
            self.c.execute(f"DELETE FROM {table}")
        self.c.execute("INSERT INTO marathons (status) VALUES (1)")

    def insert_marathon_user(self, tariff, user_id, status = 1):
        self.c.execute("SELECT * FROM user_marathon WHERE user_id = (%s) and tariff =(%s)", (user_id, tariff))
        present_in_db = self.c.fetchall()
        self.get_marathon()
        curr_marathon = self.c.fetchone()[0]
        if present_in_db:
            self.c.execute("UPDATE user_marathon SET status = (%s), date = now() WHERE user_id = (%s) and tariff =(%s)",
                           (status, user_id, tariff))
        else:
            self.c.execute("INSERT INTO user_marathon  (marathon_id, status, tariff, user_id) VALUES (%s, %s, %s, %s)",
                           (curr_marathon, 1, tariff, user_id))

    def select_user_marathon_by_tariff(self, day, tariff):
        self.c.execute(
            "SELECT * FROM user_marathon WHERE date < NOW() - INTERVAL (%s) DAY and tariff = (%s) and status = 1",
            (day, tariff ))
