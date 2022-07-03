import multiprocessing as mp
import queue
import traceback
from typing import Dict, Iterable, TypeVar, Union

from ..chunk import chunk
from ..logger import get_logger
from .worker_exception import WorkerException

logger = get_logger("parallel_map")

T = TypeVar("T")
V = TypeVar("V")


def manage_communication(
    *,
    input_values: Iterable[T],
    chunk_size: int,
    input_queue: Union[mp.Queue, queue.Queue],
    output_queue: Union[mp.Queue, queue.Queue],
    unordered: bool,
    ignore_exceptions: bool,
) -> Iterable[V]:
    chunks = iter(chunk(enumerate(input_values), chunk_size=chunk_size))
    indexed_results: Dict[int, V] = {}
    next_output_index = 0
    read_input_length = 0
    is_iteration_over = False
    while not is_iteration_over or next_output_index < read_input_length:
        if not is_iteration_over:
            try:
                next_chunk = next(chunks)
                input_queue.put(next_chunk)
                read_input_length += len(next_chunk)
            except StopIteration:
                is_iteration_over = True
            except Exception as e:
                if not ignore_exceptions:
                    raise
                else:
                    logger.error(
                        f"Exception {e} encountered in input, traceback:\n{traceback.format_exc()}"
                    )

        try:
            result_chunk = output_queue.get_nowait()

            for index, value, exception in result_chunk:
                if exception is not None:
                    e, tb = exception
                    if not ignore_exceptions:
                        raise WorkerException from e
                    else:
                        logger.error(
                            f"Exception {e} encountered in worker, traceback:\n{tb}"
                        )
                if unordered:
                    yield value
                    next_output_index += 1
                else:
                    indexed_results[index] = value

            if not unordered:
                while next_output_index in indexed_results:
                    yield indexed_results[next_output_index]
                    del indexed_results[next_output_index]
                    next_output_index += 1
        except queue.Empty:
            pass
