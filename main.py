Run python main.py
Traceback (most recent call last):
ПРОВЕРКА MOEX ISS
  File "/home/runner/work/IMOEX_SETUP_SCANNER/IMOEX_SETUP_SCANNER/main.py", line 185, in <module>
    main()
  File "/home/runner/work/IMOEX_SETUP_SCANNER/IMOEX_SETUP_SCANNER/main.py", line 176, in main
    imoex = inspect_security("IMOEX")
Дата проверки: 2026-11-13
Интервал: 10 минут

=======================================================
ИНСТРУМЕНТ: IMOEX
=======================================================
            ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/runner/work/IMOEX_SETUP_SCANNER/IMOEX_SETUP_SCANNER/main.py", line 84, in inspect_security
    "time": parse_time(begin),
            ^^^^^^^^^^^^^^^^^
  File "/home/runner/work/IMOEX_SETUP_SCANNER/IMOEX_SETUP_SCANNER/main.py", line 55, in parse_time
    dt = datetime.fromisoformat(value)
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: fromisoformat: argument must be str
Error: Process completed with exit code 1.
