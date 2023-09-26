from functools import cached_property
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, urlparse
import re
import redis
import uuid 
import os
import urllib.parse

r = redis.Redis(host='localhost', port=6379, db=0)

class WebRequestHandler(BaseHTTPRequestHandler):
    @cached_property
    def url(self):
        return urlparse(self.path)
    
    @cached_property
    def query_data(self):
        return dict(parse_qsl(self.url.query))

    @cached_property
    def cookies(self):
        return SimpleCookie(self.headers.get("Cookie"))

    def set_book_cookie(self, session_id, max_age=10):
        c = SimpleCookie()
        c["session"] = session_id
        c["session"]["max-age"] = max_age
        self.send_header('Set-Cookie', c.output(header=''))

    def get_book_session(self):
        c = self.cookies
        if not c:
            print("No cookie")
            c = SimpleCookie()
            c["session"] = uuid.uuid4()
        else:
            print("Cookie found")
        return c.get("session").value

    def do_GET(self):
        method = self.get_method(self.url.path)
        if method:
            method_name, dict_params = method
            method = getattr(self, method_name)
            method(**dict_params)
            return
        else:
            self.send_error(404, "Not Found")

    def get_book_recomendation(self, session_id, book_id):
        r.rpush(session_id, book_id)
        books = r.lrange(session_id, 0, 5)
        print(session_id, books)
        all_books = [str(i+1) for i in range(4)]
        libros_leidos = [b for b in all_books if b not in
               [vb.decode() for vb in books]]
        if len(libros_leidos) != 0:
           if len(libros_leidos) <3:
             return libros_leidos[0]
           else:
              return "Tiene que haber leído al menos 3 libros para recibir recomendaciones"
        else:
           return "No hay recomendaciones disponibles"

    def get_book(self, book_id):
        session_id = self.get_book_session()
        book_recomendation = self.get_book_recomendation(session_id, book_id)
        book_page = r.get(book_id)
        if book_page:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.set_book_cookie(session_id)
            self.end_headers()
            response = f"""
            {book_page.decode()}
        <p>  SESSION: {session_id}      </p>
        <p>  Recomendación: {book_recomendation}      </p>
"""
            self.wfile.write(response.encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def get_index(self):
        session_id = self.get_book_session()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.set_book_cookie(session_id)
        self.end_headers()
        with open('html/index.html') as f:
            response = f.read()
        self.wfile.write(response.encode("utf-8"))

    def get_method(self, path):
        for pattern, method in mapping:
            match = re.match(pattern, path)
            if match:
                return (method, match.groupdict())
            
    def get_bookWord(self):
        if self.query_data and 'q' in self.query_data:
            booksB = r.sinter(self.query_data['q'].split(' '))
        lista_libros = [b.decode() for b in booksB]
        for libro in lista_libros:
            self.get_book(libro)     
        if len(lista_libros) < len(booksB):
            self.get_index()

        self.send_response(200)
        self.send_header('Content-type','text/html')
        self.end_headers()
        
#    def get_response(self,books):
#        return f"""
#    <h1> Hola Web </h1>
#    <form action="/" method = "get">
#        <label for ="q"> Busqueda </label>
#        <input type="text" name = "q" required/>
#    </forms>
#    <p>  {self.query_data}   </p>
#    <p>  {books}   </p>
#
#"""


mapping = [
            (r'^/books/(?P<book_id>\d+)$', 'get_book'),
            (r'^/$', 'get_index'),
            (r'^/busqueda$', 'get_bookWord')
        ]

if __name__ == "__main__":
    print("Server starting...")
    server = HTTPServer(("0.0.0.0", 8000), WebRequestHandler)
    server.serve_forever()
