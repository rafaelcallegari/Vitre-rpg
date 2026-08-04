import sqlite3
c = sqlite3.connect("aincrad.db")
c.execute("DELETE FROM cooldowns WHERE comando = 'boss'")
c.commit()
c.close()
print("cooldown do boss zerado")