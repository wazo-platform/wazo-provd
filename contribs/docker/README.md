To run provd in a docker please run it like :

    docker run -p 69:69/udp -p 8666:8666 -p 8667:8667 -v /config/provd/:/etc/wazo-provd/ -it wazo-provd bash

and launch the wazo-provd

    twistd -no -r epoll wazo-provd -s -v

or

    docker run --name wazo-provd -d -p 69:69/udp -p 8666:8666 -p 8667:8667 -v /config/provd/:/etc/wazo-provd/ -t wazo-provd
