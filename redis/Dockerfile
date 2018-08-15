FROM redis:alpine

COPY init-superuser.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/init-superuser.sh

CMD /usr/local/bin/init-superuser.sh
