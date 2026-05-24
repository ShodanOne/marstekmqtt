######################### INCLUSION LIB ##########################
BASE_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
wget https://raw.githubusercontent.com/NebzHB/dependance.lib/master/dependance.lib --no-cache -O ${BASE_DIR}/dependance.lib &>/dev/null
PLUGIN=$(basename "$(realpath ${BASE_DIR}/..)")
LANG_DEP=en
. ${BASE_DIR}/dependance.lib
##################################################################
wget https://raw.githubusercontent.com/NebzHB/dependance.lib/master/pyenv.lib --no-cache -O ${BASE_DIR}/pyenv.lib &>/dev/null
. ${BASE_DIR}/pyenv.lib
##################################################################

############ Recuperation lib marstek_local_api ###############
TRDPARTY_DIR=$(realpath ${BASE_DIR}/../3rdparty)
API_DIR=$(realpath ${TRDPARTY_DIR}/marstek_local_api)
cd ${TRDPARTY_DIR}
if [ -d ${API_DIR} ]
then
    rm -R marstek_local_api
fi
wget https://github.com/jaapp/ha-marstek-local-api/archive/refs/heads/master.zip
unzip master.zip
mv ha-marstek-local-api-master/custom_components/marstek_local_api marstek_local_api
rm -R ha-marstek-local-api-master
rm unzip master.zip

TARGET_PYTHON_VERSION="3.11"
# VENV_DIR=${BASE_DIR}/venv
# APT_PACKAGES="first1 second2"

launchInstall
