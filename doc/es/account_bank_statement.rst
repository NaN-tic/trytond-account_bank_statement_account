#:before:account_bank_statement/account_bank_statement:bullet_list:concile#

* |transaction_lines|: Aquí introduciremos la información de los apuntes que
  actuarán como contrapartida a la línea del extracto. Es decir, indicaremos
  los importes y cuentas de los apuntes que anotaremos contra el apunte que
  generará la línea en la cuenta 572x. Podremos poner tantas líneas en el
  campo como queramos, pero el importe total deberá coincidir con el importe
  de la línea para poder conciliarla. Una vez contabilizada, el campo
  |bank_lines| se rellenará automáticamente con el apunte 572x correspondiente.

#:inside:account_bank_statement/account_bank_statement:section:ejemplos#

Conciliar dos movimientos de un mismo extracto
**********************************************

Si los movimientos son de gastos, se ponen los dos movimientos a la cuenta 6XX
a través de las |transaction_lines| y ya está. No será necesario conciliar ya
que las cuentas de gastos no son conciliables.

Si los movimientos son de cliente, lo mejor es ponerlos con la cuenta 43X que
corresponda y luego conciliarlos manualmente.

Movimientos con comisiones incluidas
************************************

Algunos bancos no desglosan las comisiones aplicadas en un movimiento
adicional, sino que simplemente se encargan de cargar las comisiones en la
misma línea. Esto va a producir que el botón buscar no encuentre los
movimientos correspondientes. De todos modos, podemos solucionar esto
introduciendo en el apartado |transaction_lines| el importe correspondiente a
la comisión (junto con la cuenta al que debemos contabilizar) y luego pulsar el
botón buscar de nuevo. Cómo el botón buscar busca por el importe pendiente de
contabilizar y ya hemos introducido la línea con la comisión, estaremos
buscando por el importe del pago y luego nos encontrará los movimientos
correctos.

.. |transaction_lines| field:: account.bank.statement.line/lines
.. |bank_lines| field:: account.bank.statement.line/bank_lines
.. |counterpart_lines| field:: account.bank.statement.line/counterpart_lines