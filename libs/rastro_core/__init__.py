"""Capa comun de Rastro.

Concentra los controles que el documento de proyecto declara criticos:

* ``repository``  filtro obligatorio por organizacion (riesgo R-05).
* ``state_machine`` transiciones validas del ciclo de vida (REQ-03).
* ``audit``       bitacora encadenada por funciones hash (REQ-08).
* ``authz``       matriz de autorizacion por grupo (REQ-07).

Ningun microservicio construye consultas por su cuenta: todos pasan por aqui.
"""

__version__ = "0.1.0"
