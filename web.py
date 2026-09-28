import os
import json
import subprocess
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

app = Flask(__name__)
app.secret_key = "super_secret_trading_key"

bot_process = None

def get_git_commits():
    """Получает последние 10 коммитов из Git."""
    try:
        result = subprocess.run(
            ['git', 'log', '-10', '--pretty=format:%H|%s|%cd', '--date=short'],
            capture_output=True, text=True, check=True
        )
        commits = []
        for line in result.stdout.strip().split('\n'):
            if line:
                hash_val, message, date = line.split('|', 2)
                commits.append({'hash': hash_val, 'message': message, 'date': date})
        return commits
    except subprocess.CalledProcessError:
        return []
    except FileNotFoundError:
        return []

KILL_SWITCH_FILE = "kill_switch.flag"

@app.route('/')
def index():
    status = "Запущен" if bot_process and bot_process.poll() is None else "Остановлен"
    commits = get_git_commits()
    kill_switch_active = os.path.exists(KILL_SWITCH_FILE)
    return render_template('index.html', status=status, commits=commits, kill_switch_active=kill_switch_active)

@app.route('/toggle_kill_switch', methods=['POST'])
def toggle_kill_switch():
    if os.path.exists(KILL_SWITCH_FILE):
        os.remove(KILL_SWITCH_FILE)
        flash("Kill Switch ДЕАКТИВИРОВАН. Бот возобновит работу.", "success")
    else:
        with open(KILL_SWITCH_FILE, 'w') as f:
            f.write("Manual activation")
        flash("ВНИМАНИЕ! Kill Switch АКТИВИРОВАН. Торговля остановлена!", "danger")
    return redirect(url_for('index'))

@app.route('/api/dashboard')
def api_dashboard():
    """Возвращает текущее состояние бота для инфографики (список инструментов)."""
    try:
        if os.path.exists("bot_state.json"):
            with open("bot_state.json", "r", encoding="utf-8") as f:
                state = json.load(f)
                return jsonify(state)
        else:
            return jsonify({"error": "Данные пока не собраны"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/update_instrument', methods=['POST'])
def update_instrument():
    """Обновляет настройки для конкретного инструмента."""
    try:
        data = request.json
        ticker = data.get("ticker")
        
        # Читаем текущие настройки
        settings = {"instruments": {}}
        if os.path.exists("settings.json"):
            with open("settings.json", "r", encoding="utf-8") as f:
                settings = json.load(f)
                
        if "instruments" not in settings:
            settings["instruments"] = {}
            
        if ticker not in settings["instruments"]:
            settings["instruments"][ticker] = {}
            
        # Обновляем переданные поля
        if "active" in data:
            settings["instruments"][ticker]["active"] = bool(data["active"])
        if "max_lots" in data:
            settings["instruments"][ticker]["max_lots"] = int(data["max_lots"])
        if "max_trades" in data:
            settings["instruments"][ticker]["max_trades"] = int(data["max_trades"])
            
        with open("settings.json", "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
            
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/logs')
def get_logs():
    """Возвращает последние 50 строк из файла bot.log"""
    log_file_path = 'bot.log'
    if not os.path.exists(log_file_path):
        return {"logs": "Лог файл пока не создан. Запустите бота."}
    
    try:
        # errors='replace' спасет от ошибки с кодировкой (например, если Windows пишет кириллицу в cp1251)
        with open(log_file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            # Берем последние 50 строк
            last_lines = lines[-50:]
            return {"logs": "".join(last_lines)}
    except Exception as e:
        return {"logs": f"Ошибка чтения логов: {str(e)}"}

@app.route('/update', methods=['POST'])
def update_code():
    """Выполняет git pull для получения последних обновлений с GitHub"""
    try:
        result = subprocess.run(
            ['git', 'pull', 'origin', 'main'], 
            capture_output=True, text=True, check=True
        )
        flash(f"Обновление успешно загружено!\n{result.stdout}", "success")
    except subprocess.CalledProcessError as e:
        flash(f"Ошибка при обновлении: {e.stderr if e.stderr else str(e)}", "danger")
    return redirect(url_for('index'))

@app.route('/start', methods=['POST'])
def start_bot():
    global bot_process
    if bot_process is None or bot_process.poll() is not None:
        try:
            # Запускаем бота в фоновом процессе
            # Перенаправляем логи в файл
            log_file = open('bot.log', 'a')
            bot_process = subprocess.Popen(
                ['python3', 'main.py'], 
                stdout=log_file, 
                stderr=log_file
            )
            flash("Бот успешно запущен!", "success")
        except Exception as e:
            flash(f"Ошибка при запуске: {str(e)}", "danger")
    else:
        flash("Бот уже запущен.", "warning")
    return redirect(url_for('index'))

@app.route('/stop', methods=['POST'])
def stop_bot():
    global bot_process
    if bot_process and bot_process.poll() is None:
        bot_process.terminate()
        bot_process.wait()
        flash("Бот остановлен.", "info")
    else:
        flash("Бот не запущен.", "warning")
    return redirect(url_for('index'))

@app.route('/restart', methods=['POST'])
def restart_bot():
    stop_bot()
    start_bot()
    return redirect(url_for('index'))

@app.route('/rollback', methods=['POST'])
def rollback():
    commit_hash = request.form.get('commit_hash')
    if not commit_hash:
        flash("Коммит не выбран", "danger")
        return redirect(url_for('index'))
        
    try:
        # Останавливаем бота перед откатом
        stop_bot()
        # Выполняем жесткий откат (hard reset)
        subprocess.run(['git', 'reset', '--hard', commit_hash], check=True, capture_output=True)
        flash(f"Код успешно откачен к версии {commit_hash[:7]}.", "success")
        # После отката требуется перезапуск веб-сервера или самого бота. Запустим бота:
        start_bot()
    except subprocess.CalledProcessError as e:
        flash(f"Ошибка при откате: {e.stderr.decode('utf-8') if e.stderr else str(e)}", "danger")
        
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Запускаем локальный сервер на порту 5000
    app.run(host='127.0.0.1', port=5000, debug=True)
