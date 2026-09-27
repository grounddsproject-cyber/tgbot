import os

url = os.getenv("DATABASE_URL", "")
print(f"Длина строки: {len(url)}")
print(f"Содержимое: '{url}'")
print(f"Начинается с postgresql://: {url.startswith('postgresql://')}")

# Проверяем на эмодзи и лишние символы
for i, char in enumerate(url):
    if ord(char) > 127:
        print(f"⚠️ Найден не-ASCII символ на позиции {i}: '{char}' (код {ord(char)})")

# Проверяем формат
if "postgresql://" in url and "@" in url and ":" in url.split("@")[0]:
    print("✅ Формат строки похож на правильный")
else:
    print("❌ Формат строки неправильный")
