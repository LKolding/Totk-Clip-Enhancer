class ROI: 
    x = 736
    y = 717
    w = 449
    h = 51
    img_size = (108, 36)
    
    # ---------------------------------------------------------
    # ----- These location values are relative to the ROI -----
    # ---------------------------------------------------------
    
    # Three positions when drop button 'X' is present and not, and
    back_button_location1 = (337, 6)
    back_button_location2 = (258, 6)
    # Select 'button' location
    back_button_location3 = (97, 6)
    back_button_location4 = (78, 6)
    
    button_locations = (back_button_location1, back_button_location2, back_button_location3, back_button_location4)

class AbilitiesROI:
    x = 988
    y = 783
    w = 121
    h = 54
    # dimensions, scale, width/height, whatever you wanna call it
    img_size = (108, 36) 
    
    back_button_location = (6, 10)
    
class InventoryROI:
    x = 1730
    y = 1023
    w = 115
    h = 45
    
    hold_button_location = (12, 3)
    
    img_size = (100, 39)
    
class SortbuttonROI:
    x = 374
    y = 710
    w = 165
    h = 70
    
    sort_button_location = (11, 8)
    sort_button_location2 = (12, 8)
    
    img_size = (139, 50)