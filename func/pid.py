import logging
import os
import time

class PIDController:
    def __init__(
        self,
        Kp,
        Ki,
        Kd,
        setpoint,
        sample_time=0.01,
        output_limits=(0, 100),
        initial_output=None,
        filter_alpha=0.2,
        deadband=0.15,
        output_step=0.5,
        integral_term_limits=(-3.0, 3.0),
        integral_zone_factor=0.25,
        max_delta=1.0,
        direction="direct",
        name=None,
    ):
        """
        Inicializa el controlador PID.
        
        Parámetros:
        - Kp: Ganancia proporcional
        - Ki: Ganancia integral
        - Kd: Ganancia derivativa
        - setpoint: Valor deseado (referencia)
        - sample_time: Tiempo de muestreo en segundos
        - output_limits: Límites de salida del controlador (min, max)
        - initial_output: salida inicial del PID (opcional)
        - filter_alpha: Alfa del filtro EMA para la PV (0-1)
        - deadband: Banda muerta alrededor del setpoint
        - output_step: Paso de cuantización de salida (%)
        - integral_term_limits: Limite del termino integral (min, max)
        - integral_zone_factor: Factor de integracion cerca del setpoint
        - name: Identificador del PID para logging
        """
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.setpoint = setpoint
        self.sample_time = sample_time
        self.output_limits = output_limits
        self.filter_alpha = filter_alpha
        self.deadband = deadband
        self.output_step = output_step
        self.integral_term_limits = integral_term_limits
        self.integral_zone_factor = integral_zone_factor
        self.last_output = 0.0
        self.max_delta_output = max_delta
        self.direction = self._normalize_direction(direction)
        self.name = name or f"PID_{id(self)}"
        self.logger = logging.getLogger(self.name)
        self.logger.propagate = False
        # Ensure only one file handler per PID log file
        pid_log_file = "logs/pid.log"
        os.makedirs(os.path.dirname(pid_log_file), exist_ok=True)
        if not any(isinstance(h, logging.FileHandler) and h.baseFilename.endswith("pid.log") for h in self.logger.handlers):
            handler = logging.FileHandler(pid_log_file)
            formatter = logging.Formatter(f'%(asctime)s %(levelname)s [{self.name}] %(message)s')
            handler.setFormatter(formatter)
            handler.setLevel(logging.INFO)
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        
        self.reset(initial_output=initial_output)

    @staticmethod
    def _normalize_direction(direction):
        if isinstance(direction, str):
            val = direction.strip().lower()
            if val in ("direct", "directa", "normal"):
                return "direct"
            if val in ("reverse", "reversa", "inversa", "invert", "inverse"):
                return "reverse"
        return "direct"

    def set_direction(self, direction):
        self.direction = self._normalize_direction(direction)
    
    def reset(self, initial_output=None):
        """Reinicia el controlador (borra la memoria integral y derivativa)."""
        self.last_error = 0
        self.integral = 0
        self.last_time = time.time()
        # El valor filtrado se inicializa en la primera lectura válida.
        self.pv_filtered = None
        if initial_output is not None:
            self.last_output = initial_output
    
    def update(self, measured_value):
        """
        Calcula la salida del controlador PID basado en el valor medido,
        limitando el cambio máximo del output por ciclo.
        """
        if measured_value is None:
            return None

        current_time = time.time()
        delta_time = current_time - self.last_time

        if delta_time < self.sample_time:
            return None

        pv_raw = measured_value
        # Filtro EMA sobre PV para suavizar ruido.
        if self.pv_filtered is None:
            self.pv_filtered = pv_raw
        else:
            try:
                alpha = float(self.filter_alpha)
            except (TypeError, ValueError):
                alpha = 0.0
            alpha = max(0.0, min(1.0, alpha))
            self.pv_filtered = self.pv_filtered + alpha * (pv_raw - self.pv_filtered)

        sign = -1.0 if self.direction == "reverse" else 1.0
        error = sign * (self.setpoint - self.pv_filtered)

        try:
            deadband = float(self.deadband)
        except (TypeError, ValueError):
            deadband = 0.0
        deadband = abs(deadband)
        abs_error = abs(error)

        try:
            min_i_term, max_i_term = self.integral_term_limits
        except Exception:
            min_i_term, max_i_term = -3.0, 3.0
        try:
            min_i_term = float(min_i_term)
        except (TypeError, ValueError):
            min_i_term = -3.0
        try:
            max_i_term = float(max_i_term)
        except (TypeError, ValueError):
            max_i_term = 3.0
        if min_i_term > max_i_term:
            min_i_term, max_i_term = max_i_term, min_i_term

        try:
            integral_zone_factor = float(self.integral_zone_factor)
        except (TypeError, ValueError):
            integral_zone_factor = 0.25
        if integral_zone_factor < 0:
            integral_zone_factor = 0.0

        if abs_error < deadband:
            proportional = 0.0
            derivative = 0.0
            integral_term = self.Ki * self.integral
            if integral_term < min_i_term:
                integral_term = min_i_term
            elif integral_term > max_i_term:
                integral_term = max_i_term
            if self.Ki != 0:
                self.integral = integral_term / self.Ki
            else:
                self.integral = 0.0
            delta_u = 0.0
            output = self.last_output

            # Guardar valores para la próxima iteración
            self.last_error = error
            self.last_time = current_time
            self.last_output = output

            self.logger.info(
                "SP=%.2f PV=%.2f PVf=%.2f Err=%.2f P=%.2f I=%.2f D=%.2f dU=%.2f Out=%.2f Ilim=(%.2f,%.2f) Izf=%.2f Dir=%s",
                self.setpoint,
                pv_raw,
                self.pv_filtered,
                error,
                proportional,
                integral_term,
                derivative,
                delta_u,
                output,
                min_i_term,
                max_i_term,
                integral_zone_factor,
                self.direction,
            )

            if output is None:
                output = 0.0
            return output

        # PID terms (incremental form)
        proportional = self.Kp * error
        derivative = 0.0
        if delta_time > 0:
            derivative = self.Kd * (error - self.last_error) / delta_time

        integral_increment = error * delta_time
        if deadband > 0 and abs_error < 2 * deadband:
            integral_increment = error * delta_time * integral_zone_factor
        integral_candidate = self.integral + integral_increment
        integral_term_candidate = self.Ki * integral_candidate
        if integral_term_candidate < min_i_term:
            integral_term_candidate = min_i_term
        elif integral_term_candidate > max_i_term:
            integral_term_candidate = max_i_term
        if self.Ki != 0:
            integral_candidate = integral_term_candidate / self.Ki
        else:
            integral_candidate = 0.0
        delta_u_candidate = proportional + integral_term_candidate + derivative

        # Salida candidata para decidir anti-windup.
        output_candidate = self.last_output + delta_u_candidate

        # Rate limit (% por ciclo)
        if self.max_delta_output is not None and self.max_delta_output > 0:
            du = output_candidate - self.last_output
            if abs(du) > self.max_delta_output:
                output_candidate = self.last_output + self.max_delta_output * (1 if du > 0 else -1)

        # Clamp para evaluar saturación
        min_limit, max_limit = self.output_limits
        output_limited = output_candidate
        clamped = False
        if min_limit is not None and output_limited < min_limit:
            output_limited = min_limit
            clamped = True
        if max_limit is not None and output_limited > max_limit:
            output_limited = max_limit
            clamped = True

        # Anti-windup: no integrar si estamos saturados y el error empuja más la saturación.
        if not clamped:
            self.integral = integral_candidate
        else:
            if output_limited == min_limit and error < 0:
                pass
            elif output_limited == max_limit and error > 0:
                pass
            else:
                self.integral = integral_candidate

        integral_term = self.Ki * self.integral
        if integral_term < min_i_term:
            integral_term = min_i_term
        elif integral_term > max_i_term:
            integral_term = max_i_term
        if self.Ki != 0:
            self.integral = integral_term / self.Ki
        else:
            self.integral = 0.0
        delta_u = proportional + integral_term + derivative

        # Salida final (rate limit + clamp + cuantización)
        output = self.last_output + delta_u

        if self.max_delta_output is not None and self.max_delta_output > 0:
            du = output - self.last_output
            if abs(du) > self.max_delta_output:
                output = self.last_output + self.max_delta_output * (1 if du > 0 else -1)

        output_clamped = output
        if min_limit is not None and output_clamped < min_limit:
            output_clamped = min_limit
        if max_limit is not None and output_clamped > max_limit:
            output_clamped = max_limit
        output = output_clamped

        try:
            step = float(self.output_step)
        except (TypeError, ValueError):
            step = 0.0
        if step > 0:
            output = round(output / step) * step
            if min_limit is not None and output < min_limit:
                output = min_limit
            if max_limit is not None and output > max_limit:
                output = max_limit

        # Guardar valores para la próxima iteración
        self.last_error = error
        self.last_time = current_time
        self.last_output = output

        self.logger.info(
            "SP=%.2f PV=%.2f PVf=%.2f Err=%.2f P=%.2f I=%.2f D=%.2f dU=%.2f Out=%.2f Ilim=(%.2f,%.2f) Izf=%.2f Dir=%s",
            self.setpoint,
            pv_raw,
            self.pv_filtered,
            error,
            proportional,
            integral_term,
            derivative,
            delta_u,
            output,
            min_i_term,
            max_i_term,
            integral_zone_factor,
            self.direction,
        )

        # If output is None return 0
        if output is None:
            output = 0.0
        return output
