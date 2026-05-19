class LinkerNode:
    """A node in a linked list used for building a queue.

    Attributes:
        value (any): The data stored in the node.
        next_node (LinkerNode, optional): Reference to the next node in the sequence. Defaults to None.
    """

    def __init__(self, value: any, next_node=None):
        self.value = value
        self.next_node = next_node


class Queue:
    """A standard First-In-First-Out (FIFO) queue implemented using a linked list.

    This class manages a sequence of elements where elements are added to the back (tail)
    and removed from the front (head).

    Attributes:
        head (LinkerNode | None): The front of the queue (where items are dequeued).
        tail (LinkerNode | None): The end of the queue (where items are enqueued).
    """

    def __init__(self):
        """Initializes an empty queue."""
        self.head = None
        self.tail = None
        self.count = 0

    def enqueue(self, value: any):
        """Adds a new item to the back (tail) of the queue.

        Args:
            value (any): The data to be added to the queue.
        """
        # first insert.

        if self.count == 0:
            self.head = LinkerNode(value)
            self.tail = self.head
        else:
            new_node = LinkerNode(value)
            self.tail.next_node = new_node
            self.tail = new_node
        self.count += 1

    def dequeue(self) -> any:
        """Removes and returns the item from the front (head) of the queue.

        Returns:
            any: The data from the front of the queue.

        Raises:
            IndexError: If the queue is empty.
        """
        if self.count == 0:
            raise IndexError("The queue is empty.")

        value = self.head.value
        self.head = self.head.next_node
        self.count -= 1
        return value

    def peek(self) -> any:
        """Returns the item at the front of the queue without removing it.

        Returns:
            any: The data at the front of the queue.

        Raises:
            IndexError: If the queue is empty.
        """
        if self.count == 0:
            raise IndexError("The queue is empty.")
        return self.head.value

    def is_empty(self) -> bool:
        """Checks if the queue contains any elements.

        Returns:
            bool: True if the queue is empty, False otherwise.
        """
        return self.count == 0


class HeapNode:
    """A node object for the heap, storing data and its priority weight.

    Attributes:
        weight (int/float): The priority weight of the node.
        data (any): The actual data/notification.
    """

    def __init__(self, weight, data):
        self.weight = weight
        self.data = data

    def __lt__(self, other):
        # use for min heap or custome sort logic
        return self.weight < other.weight


class PriorityQueue:
    """A priority queue implemented using a linked list with .

    This class manages items based on their priority weight rather than
    First-In-First-Out order.

    Attributes:
        _heap (list[HeapNode]): The underlying list used to store heap nodes.
    """

    def __init__(self):
        """Initializes an empty priority queue."""
        self._heap = []

    def __get_left_child(self, index):
        return 2 * index + 1

    def __get_right_child(self, index):
        return 2 * index + 2

    def __get_parent(self, index):
        return (index - 1) // 2

    def __swap(self, index1, index2):
        self._heap[index1], self._heap[index2] = self._heap[index2], self._heap[index1]

    def __shit_up(self, index):
        """
        small helper function to shift up an index node
        """
        parent_index = self.__get_parent(index)
        while index > 0 and self._heap[index] < self._heap[parent_index]:
            self.__swap(index, parent_index)
            index = parent_index
            parent_index = self.__get_parent(index)

    def __shit_down(self, index):
        """
        small helper function to shift down an index node
        """
        left_child_index = self.__get_left_child(index)
        right_child_index = self.__get_right_child(index)

        smallest_index = index

        if (
            left_child_index < len(self._heap)
            and self._heap[left_child_index] < self._heap[smallest_index]
        ):
            smallest_index = left_child_index

        if (
            right_child_index < len(self._heap)
            and self._heap[right_child_index] < self._heap[smallest_index]
        ):
            smallest_index = right_child_index

        if smallest_index != index:
            self.__swap(index, smallest_index)
            self.__shit_down(smallest_index)

    def push(self, weight: float, data: any):
        """Pushes a new item into the priority queue.

        Args:
            weight (float): The priority weight of the item.
            data (any): The content to be stored.
        """
        new_node = HeapNode(weight, data)
        self._heap.append(new_node)
        self.__shit_up(len(self._heap) - 1)

    def pop(self) -> any:
        """Pops the item with the highest priority.

        Returns:
            any: The data of the highest priority item.

        Raises:
            IndexError: If the priority queue is empty.
        """
        if len(self._heap) == 0:
            raise IndexError("The priority queue is empty.")

        self.__swap(0, len(self._heap) - 1)
        value = self._heap.pop()
        self.__shit_down(0)
        return value.data

    def peek(self) -> any:
        """Returns the highest priority item without removing it.

        Returns:
            any: The data of the highest priority item.

        Raises:
            IndexError: If the priority queue is empty.
        """
        return self._heap[0].data if len(self._heap) > 0 else None
