FROM python:3.6-stretch

RUN pip install pipenv

WORKDIR /demo
COPY Pipfile /demo/Pipfile
COPY Pipfile.lock /demo/Pipfile.lock
RUN pipenv install --system --deploy

COPY *.py /demo/

ENTRYPOINT ["python", "/demo/demo.py"]