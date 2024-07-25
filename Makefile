BIN := .venv/Scripts/
PIP := $(BIN)/pip3
PYTHON := $(BIN)/python
TESTS := tests/
SRC := src/
RES := $(SRC)/res/

QRC_FOLDER := $(SRC)/qrc
QRC_FILES := $(wildcard $(RES)/*.qrc)
COMP_QRC_FILES := $(patsubst $(RES)/%.qrc,$(QRC_FOLDER)/%.py,$(QRC_FILES))

all: $(COMP_QRC_FILES) requirements.txt
	$(PYTHON) -m unittest discover -s $(TESTS)

requirements.txt: FORCE
	$(PIP) freeze > $@

$(QRC_FOLDER)/%.py: $(RES)/%.qrc
	pyrcc5 $< -o $@

FORCE: ;
