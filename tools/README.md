This tool can be used to create PBKDF2 hashed passwords to store in redis for user authentication.

To allow a superuser to connect to the mosquitto broker:

1. Run the `np` executable to create a PBKDF2 hashed password
   ```
   $ ./np -p 123
   PBKDF2$sha256$901$x3RPLXFz3ateaMpJ$8eu+hGM+2XiqCUo3FzfaV7ck7RExX40s
   ```
2. Add the user to redis with the computed password hash, e.g.
   ```
   redis-cli> SET admin PBKDF2$sha256$901$x3RPLXFz3ateaMpJ$8eu+hGM+2XiqCUo3FzfaV7ck7RExX40s
   ```
3. Connect to the broker to subscribe or publish:
   ```
   $ mosquitto_pub --username admin --password 123 --topic "test" -m "Hello"
   ```