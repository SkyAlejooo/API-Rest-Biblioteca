from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Autor, Libro, Prestamo
from .serializers import AutorSerializer, LibroSerializer, PrestamoSerializer
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone


class AutorViewSet(viewsets.ModelViewSet):
    queryset = Autor.objects.all()
    serializer_class = AutorSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['nacionalidad']
    search_fields = ['nombre', 'apellido']
    ordering_fields = ['nombre', 'fecha_nacimiento']
    ordering = ['apellido', 'nombre']


class LibroViewSet(viewsets.ModelViewSet):
    queryset = Libro.objects.select_related('autor')
    serializer_class = LibroSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['genero', 'disponible', 'autor']
    search_fields = ['titulo', 'autor__nombre', 'autor__apellido']
    ordering_fields = ['titulo', 'fecha_publicacion']
    ordering = ['-fecha_publicacion']

    @action(detail=False, methods=['get'])
    def disponibles(self, request):
        """Endpoint personalizado para obtener solo libros disponibles"""
        libros_disponibles = self.queryset.filter(disponible=True)
        serializer = self.get_serializer(libros_disponibles, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def prestar(self, request, pk=None):
        """Endpoint para prestar un libro"""
        libro = self.get_object()

        if not libro.disponible:
            return Response(
                {'error': 'Libro no disponible'},
                status=status.HTTP_400_BAD_REQUEST
            )

        prestamo = Prestamo.objects.create(
            libro=libro,
            usuario=request.user
        )

        libro.disponible = False
        libro.save()

        return Response({'mensaje': f'Libro "{libro.titulo}" prestado exitosamente'})


class PrestamoViewSet(viewsets.ModelViewSet):
    serializer_class = PrestamoSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['devuelto', 'usuario']
    ordering = ['-fecha_prestamo']
    permission_classes = [IsAuthenticated]  # Asegura que el usuario esté autenticado

    def get_queryset(self):
        # Los usuarios solo pueden ver sus propios préstamos
        if self.request.user.is_staff:
            return Prestamo.objects.all()

        if self.request.user.is_authenticated:
            return Prestamo.objects.filter(usuario=self.request.user)

        return Prestamo.objects.none()  # Si no está autenticado, no devolver nada
    
    @action(detail=True, methods=['post'])
    def devolver(self, request, pk=None):
        """Endpoint para devolver un libro"""
        try:
            prestamo = self.get_object()

            if prestamo.devuelto:
                return Response(
                    {'error': 'El libro ya ha sido devuelto'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            prestamo.devuelto = True
            prestamo.fecha_devolucion = timezone.now()
            prestamo.save()

            libro = prestamo.libro
            libro.disponible = True
            libro.save()

            return Response(
                {
                    'mensaje': f'Libro "{libro.titulo}" devuelto exitosamente',
                    'prestamo': {
                        'id': prestamo.id,
                        'libro': prestamo.libro.id,
                        'libro_titulo': prestamo.libro.titulo,
                        'usuario': prestamo.usuario.id,
                        'usuario_username': prestamo.usuario.username,
                        'fecha_prestamo': prestamo.fecha_prestamo,
                        'fecha_devolucion': prestamo.fecha_devolucion,
                        'devuelto': prestamo.devuelto
                    }
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': f'Ocurrió un error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )