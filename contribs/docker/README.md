To run provd in a docker please run it like :

    docker run -p 69:69/udp -p 8666:8666 -p 8667:8667 -v /config/provd/:/etc/xivo/provd/ -it xivo-provd /bin/bash

and launch the xivo-provd

    twistd -no -r epoll xivo-provd -s -v

or

    docker run -d -p 69:69/udp -p 8666:8666 -p 8667:8667 -v /config/ctid/:/etc/xivo/provd/conf.d -t xivo-provd
