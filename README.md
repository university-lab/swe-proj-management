# swe-proj-management

### setup v-env
python3 -m venv .venv
source .venv/Scripts/activate

### install requirements
pip install -r requirements.txt

### setup (v)env variables
vim .venv/Scripts/activate
export SQL_URI="mysql+pymysql://root:root@localhost:3306/project_management"
export SQL_TEST_URI="${SQL_URI}_test"

### make & run
cd path/to/wd
make
./run.sh


