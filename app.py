from datetime import datetime, timedelta

def clean_old_history(data):
    """90 days (3 months) se purani history auto delete karega"""
    cutoff_date = datetime.now(IST) - timedelta(days=90)
    for host in data.get("history", {}):
        filtered = []
        for item in data["history"][host]:
            try:
                item_time = datetime.strptime(item["timestamp"], "%Y-%m-%d %I:%M:%S %p")
                item_time = IST.localize(item_time)
                if item_time >= cutoff_date:
                    filtered.append(item)
            except Exception:
                filtered.append(item)
        data["history"][host] = filtered
    return data

@app.route("/api/system/history", methods=["GET", "POST", "DELETE"])
def system_history():
    data = load_data()
    data = clean_old_history(data)
    
    if request.method == "POST":
        req = request.json or {}
        hostname = req.get("hostname")
        url = req.get("url")
        timestamp = req.get("timestamp", get_ist_time())
        
        if hostname and url:
            if hostname not in data["history"]:
                data["history"][hostname] = []
            # Duplicate URL continuously log hone se rokne ke liye
            if not data["history"][hostname] or data["history"][hostname][-1]["url"] != url:
                data["history"][hostname].append({"url": url, "timestamp": timestamp})
                save_data(data)
        return jsonify({"status": "logged"})
        
    elif request.method == "GET":
        hostname = request.args.get("hostname")
        if hostname:
            return jsonify({"hostname": hostname, "history": data["history"].get(hostname, [])})
        return jsonify({"history": data.get("history", {})})
