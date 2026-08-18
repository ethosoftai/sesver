.PHONY: demo bench poison test lint clean

demo:            ## Uctan uca canli akis simulasyonu (bagimlilik gerekmez)
	python -m sesver.cli demo --messages 2000 --seed 42

bench:           ## DIVAN-Bench: tam degerlendirme kosumu
	python -m sesver.cli bench --messages 20000 --seed 7

poison:          ## Zehirleme testi: sahte kayitlar kuyrukta ne kadar bastiriliyor
	python -m sesver.cli poison --messages 20000 --poison 200 --seed 13

test:
	python -m pytest -q

lint:
	ruff check src tests

clean:
	rm -rf .pytest_cache .ruff_cache __pycache__ runs/
