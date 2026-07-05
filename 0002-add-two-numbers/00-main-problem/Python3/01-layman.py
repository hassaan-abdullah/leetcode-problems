from typing import Optional

class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

class Solution:
    def addTwoNumbers(self, l1: Optional[ListNode], l2: Optional[ListNode]) -> Optional[ListNode]:
        fNum = 0
        sNum = 0

        aNum = 0

        L1 = linked_list_to_list(l1)
        L2 = linked_list_to_list(l2)

        for i in range(len(L1)):
            fNum += 10**i * L1[i]
        
        for i in range(len(L2)):
            sNum += 10**i * L2[i]
        
        aNum = fNum + sNum

        final = [int(digit) for digit in str(aNum)[::-1]]

        return list_to_linked_list(final)

def linked_list_to_list(head):
    result = []
    current = head

    while current is not None:
        result.append(current.val)
        current = current.next

    return result

def list_to_linked_list(py_list):
    if not py_list:
        return None
    
    head = ListNode(py_list[0])
    current = head

    for item in py_list[1:]:
        current.next = ListNode(item)
        current = current.next
    
    return head