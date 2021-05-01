set -e
coverage run -m unittest RunTests $@
coverage report
coverage html
